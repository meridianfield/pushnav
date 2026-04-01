/*
 * Copyright (C) 2026 Arun Venkataswamy
 *
 * This file is part of PushNav.
 *
 * PushNav is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * PushNav is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with PushNav. If not, see <https://www.gnu.org/licenses/>.
 */

/*
 * camera_server.c — Linux V4L2 camera server
 *
 * Self-contained C replacement for camera_server.py.  Captures MJPEG frames
 * from the target USB camera (VID 0x32E6, PID 0x9251) via V4L2 mmap and
 * serves them over TCP using the same binary protocol as the macOS Swift
 * camera server (see specs/start/SPEC_PROTOCOL_CAMERA.md).
 *
 * Build: gcc -Wall -Wextra -O2 -o camera_server camera_server.c -ljpeg
 */

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <jpeglib.h>

/* ------------------------------------------------------------------ */
/* Protocol constants                                                  */
/* ------------------------------------------------------------------ */

#define MSG_HELLO         0x00
#define MSG_FRAME         0x01
#define MSG_CONTROL_INFO  0x02
#define MSG_ERROR         0x03
#define MSG_SET_CONTROL   0x11
#define MSG_GET_CONTROLS  0x12

#define HEADER_SIZE       8

/* ------------------------------------------------------------------ */
/* Configuration                                                       */
/* ------------------------------------------------------------------ */

#define TARGET_VID   0x32E6
#define TARGET_PID   0x9251
#define CAPTURE_W    1280
#define CAPTURE_H    720
#define NUM_BUFFERS  4
#define SERVER_PORT  8764

/* ------------------------------------------------------------------ */
/* V4L2 state                                                          */
/* ------------------------------------------------------------------ */

static int cam_fd = -1;
static int use_mjpeg = 1;

struct mmap_buf {
    void  *start;
    size_t length;
};

static struct mmap_buf buffers[NUM_BUFFERS];
static unsigned int n_buffers = 0;

/* Camera model name from sysfs */
static char camera_model[128] = "Unknown";

/* Control ranges */
typedef struct {
    int valid;
    int32_t min, max, step, defval, cur;
} ctrl_range_t;

static ctrl_range_t exposure_range;
static ctrl_range_t gain_range;

/* Shutdown flag */
static volatile sig_atomic_t stop_flag = 0;

/* ------------------------------------------------------------------ */
/* Utility: xioctl (retry on EINTR)                                    */
/* ------------------------------------------------------------------ */

static int xioctl(int fd, unsigned long request, void *arg)
{
    int r;
    do {
        r = ioctl(fd, request, arg);
    } while (r == -1 && errno == EINTR);
    return r;
}

/* ------------------------------------------------------------------ */
/* Device discovery via sysfs                                          */
/* ------------------------------------------------------------------ */

static int find_device(char *dev_path, size_t dev_path_len)
{
    DIR *d = opendir("/sys/class/video4linux");
    if (!d)
        return -1;

    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        if (strncmp(ent->d_name, "video", 5) != 0)
            continue;

        char path[512];

        /* Read idVendor */
        snprintf(path, sizeof(path),
                 "/sys/class/video4linux/%s/device/../idVendor", ent->d_name);
        FILE *f = fopen(path, "r");
        if (!f) continue;
        char vendor[16] = {0};
        if (!fgets(vendor, sizeof(vendor), f)) { fclose(f); continue; }
        fclose(f);

        /* Read idProduct */
        snprintf(path, sizeof(path),
                 "/sys/class/video4linux/%s/device/../idProduct", ent->d_name);
        f = fopen(path, "r");
        if (!f) continue;
        char product[16] = {0};
        if (!fgets(product, sizeof(product), f)) { fclose(f); continue; }
        fclose(f);

        unsigned int vid = 0, pid = 0;
        sscanf(vendor, "%x", &vid);
        sscanf(product, "%x", &pid);

        if (vid == TARGET_VID && pid == TARGET_PID) {
            char candidate[288];
            snprintf(candidate, sizeof(candidate), "/dev/%s", ent->d_name);

            /* Verify this node supports VIDEO_CAPTURE (skip metadata nodes) */
            int test_fd = open(candidate, O_RDWR);
            if (test_fd < 0)
                continue;
            struct v4l2_capability cap;
            memset(&cap, 0, sizeof(cap));
            if (xioctl(test_fd, VIDIOC_QUERYCAP, &cap) < 0 ||
                !(cap.device_caps & V4L2_CAP_VIDEO_CAPTURE)) {
                close(test_fd);
                continue;
            }
            close(test_fd);

            snprintf(dev_path, dev_path_len, "%s", candidate);

            /* Try to read camera model name */
            snprintf(path, sizeof(path),
                     "/sys/class/video4linux/%s/name", ent->d_name);
            f = fopen(path, "r");
            if (f) {
                if (fgets(camera_model, sizeof(camera_model), f)) {
                    /* Strip trailing newline */
                    size_t len = strlen(camera_model);
                    if (len > 0 && camera_model[len - 1] == '\n')
                        camera_model[len - 1] = '\0';
                }
                fclose(f);
            }

            closedir(d);
            fprintf(stderr, "Found camera '%s' at %s\n", camera_model, dev_path);
            return 0;
        }
    }

    closedir(d);
    return -1;
}

/* ------------------------------------------------------------------ */
/* V4L2 capture setup                                                  */
/* ------------------------------------------------------------------ */

static int open_camera(const char *dev_path)
{
    cam_fd = open(dev_path, O_RDWR);
    if (cam_fd < 0) {
        perror("open camera");
        return -1;
    }

    /* Try MJPEG first */
    struct v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = CAPTURE_W;
    fmt.fmt.pix.height = CAPTURE_H;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
    fmt.fmt.pix.field = V4L2_FIELD_NONE;

    if (xioctl(cam_fd, VIDIOC_S_FMT, &fmt) == 0 &&
        fmt.fmt.pix.pixelformat == V4L2_PIX_FMT_MJPEG) {
        use_mjpeg = 1;
        fprintf(stderr, "Using MJPEG capture %ux%u\n",
                fmt.fmt.pix.width, fmt.fmt.pix.height);
    } else {
        /* Fallback to YUYV */
        memset(&fmt, 0, sizeof(fmt));
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        fmt.fmt.pix.width = CAPTURE_W;
        fmt.fmt.pix.height = CAPTURE_H;
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV;
        fmt.fmt.pix.field = V4L2_FIELD_NONE;

        if (xioctl(cam_fd, VIDIOC_S_FMT, &fmt) < 0) {
            perror("VIDIOC_S_FMT (YUYV)");
            close(cam_fd);
            cam_fd = -1;
            return -1;
        }
        use_mjpeg = 0;
        fprintf(stderr, "MJPEG not available, using YUYV capture %ux%u\n",
                fmt.fmt.pix.width, fmt.fmt.pix.height);
    }

    /* Request mmap buffers */
    struct v4l2_requestbuffers req;
    memset(&req, 0, sizeof(req));
    req.count = NUM_BUFFERS;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;

    if (xioctl(cam_fd, VIDIOC_REQBUFS, &req) < 0) {
        perror("VIDIOC_REQBUFS");
        close(cam_fd);
        cam_fd = -1;
        return -1;
    }
    n_buffers = req.count;
    if (n_buffers > NUM_BUFFERS)
        n_buffers = NUM_BUFFERS;

    /* mmap each buffer */
    for (unsigned int i = 0; i < n_buffers; i++) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;

        if (xioctl(cam_fd, VIDIOC_QUERYBUF, &buf) < 0) {
            perror("VIDIOC_QUERYBUF");
            close(cam_fd);
            cam_fd = -1;
            return -1;
        }

        buffers[i].length = buf.length;
        buffers[i].start = mmap(NULL, buf.length,
                                PROT_READ | PROT_WRITE, MAP_SHARED,
                                cam_fd, buf.m.offset);
        if (buffers[i].start == MAP_FAILED) {
            perror("mmap");
            close(cam_fd);
            cam_fd = -1;
            return -1;
        }
    }

    /* Queue all buffers */
    for (unsigned int i = 0; i < n_buffers; i++) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;

        if (xioctl(cam_fd, VIDIOC_QBUF, &buf) < 0) {
            perror("VIDIOC_QBUF");
            return -1;
        }
    }

    /* Start streaming */
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(cam_fd, VIDIOC_STREAMON, &type) < 0) {
        perror("VIDIOC_STREAMON");
        return -1;
    }

    return 0;
}

/* ------------------------------------------------------------------ */
/* V4L2 cleanup                                                        */
/* ------------------------------------------------------------------ */

static void close_camera(void)
{
    if (cam_fd < 0) return;

    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    xioctl(cam_fd, VIDIOC_STREAMOFF, &type);

    for (unsigned int i = 0; i < n_buffers; i++) {
        if (buffers[i].start && buffers[i].start != MAP_FAILED)
            munmap(buffers[i].start, buffers[i].length);
    }

    close(cam_fd);
    cam_fd = -1;
}

/* ------------------------------------------------------------------ */
/* V4L2 controls                                                       */
/* ------------------------------------------------------------------ */

static int v4l2_get_control(int ctrl_id, int32_t *value)
{
    struct v4l2_control ctrl;
    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = ctrl_id;
    if (xioctl(cam_fd, VIDIOC_G_CTRL, &ctrl) < 0)
        return -1;
    *value = ctrl.value;
    return 0;
}

static int v4l2_set_control(int ctrl_id, int32_t value)
{
    struct v4l2_control ctrl;
    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = ctrl_id;
    ctrl.value = value;
    if (xioctl(cam_fd, VIDIOC_S_CTRL, &ctrl) < 0)
        return -1;
    return 0;
}

static void query_control(uint32_t ctrl_id, ctrl_range_t *out)
{
    memset(out, 0, sizeof(*out));
    struct v4l2_queryctrl qctrl;
    memset(&qctrl, 0, sizeof(qctrl));
    qctrl.id = ctrl_id;

    if (xioctl(cam_fd, VIDIOC_QUERYCTRL, &qctrl) < 0) {
        out->valid = 0;
        return;
    }
    out->valid = 1;
    out->min = qctrl.minimum;
    out->max = qctrl.maximum;
    out->step = qctrl.step;
    out->defval = qctrl.default_value;

    int32_t cur;
    if (v4l2_get_control(ctrl_id, &cur) == 0)
        out->cur = cur;
    else
        out->cur = qctrl.default_value;
}

static void probe_controls(void)
{
    query_control(V4L2_CID_EXPOSURE_ABSOLUTE, &exposure_range);
    query_control(V4L2_CID_GAIN, &gain_range);
    fprintf(stderr, "Exposure range: valid=%d min=%d max=%d step=%d cur=%d\n",
            exposure_range.valid, exposure_range.min, exposure_range.max,
            exposure_range.step, exposure_range.cur);
    fprintf(stderr, "Gain range: valid=%d min=%d max=%d step=%d cur=%d\n",
            gain_range.valid, gain_range.min, gain_range.max,
            gain_range.step, gain_range.cur);
}

/* ------------------------------------------------------------------ */
/* YUYV → JPEG conversion (libjpeg)                                    */
/* ------------------------------------------------------------------ */

static unsigned char *jpeg_buf = NULL;
static unsigned long  jpeg_buf_size = 0;

static int yuyv_to_jpeg(const void *yuyv_data, size_t yuyv_len,
                         unsigned char **out_jpeg, unsigned long *out_len)
{
    (void)yuyv_len;
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;

    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);

    /* Output to memory */
    jpeg_buf = NULL;
    jpeg_buf_size = 0;
    jpeg_mem_dest(&cinfo, &jpeg_buf, &jpeg_buf_size);

    cinfo.image_width = CAPTURE_W;
    cinfo.image_height = CAPTURE_H;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_YCbCr;

    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, 85, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    /* Convert YUYV → YCbCr row by row */
    unsigned char *row = malloc(CAPTURE_W * 3);
    if (!row) {
        jpeg_destroy_compress(&cinfo);
        return -1;
    }

    const unsigned char *src = (const unsigned char *)yuyv_data;
    while (cinfo.next_scanline < cinfo.image_height) {
        const unsigned char *line = src + cinfo.next_scanline * CAPTURE_W * 2;
        for (int x = 0; x < CAPTURE_W; x += 2) {
            int idx = x * 2;
            unsigned char y0 = line[idx + 0];
            unsigned char cb = line[idx + 1];
            unsigned char y1 = line[idx + 2];
            unsigned char cr = line[idx + 3];
            row[x * 3 + 0] = y0;
            row[x * 3 + 1] = cb;
            row[x * 3 + 2] = cr;
            row[(x + 1) * 3 + 0] = y1;
            row[(x + 1) * 3 + 1] = cb;
            row[(x + 1) * 3 + 2] = cr;
        }
        unsigned char *row_ptr = row;
        jpeg_write_scanlines(&cinfo, &row_ptr, 1);
    }

    free(row);
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);

    *out_jpeg = jpeg_buf;
    *out_len = jpeg_buf_size;
    return 0;
}

/* ------------------------------------------------------------------ */
/* Frame capture                                                       */
/* ------------------------------------------------------------------ */

/* Returns JPEG data in *out_data, length in *out_len.
 * For MJPEG: points into mmap buffer (caller must QBUF after use).
 * For YUYV:  allocates via libjpeg (caller must free via free()).
 * Returns buf.index on success, -1 on failure.
 */
static int capture_frame(const unsigned char **out_data, size_t *out_len,
                         int *is_allocated)
{
    struct v4l2_buffer buf;
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;

    if (xioctl(cam_fd, VIDIOC_DQBUF, &buf) < 0) {
        if (errno == EAGAIN)
            return -1;
        perror("VIDIOC_DQBUF");
        return -1;
    }

    if (use_mjpeg) {
        *out_data = buffers[buf.index].start;
        *out_len = buf.bytesused;
        *is_allocated = 0;
    } else {
        unsigned char *jpeg_data = NULL;
        unsigned long jpeg_len = 0;
        if (yuyv_to_jpeg(buffers[buf.index].start, buf.bytesused,
                         &jpeg_data, &jpeg_len) < 0) {
            /* Re-queue and report failure */
            xioctl(cam_fd, VIDIOC_QBUF, &buf);
            return -1;
        }
        *out_data = jpeg_data;
        *out_len = jpeg_len;
        *is_allocated = 1;
    }

    return (int)buf.index;
}

static void requeue_buffer(int index)
{
    struct v4l2_buffer buf;
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index = (unsigned int)index;
    xioctl(cam_fd, VIDIOC_QBUF, &buf);
}

/* ------------------------------------------------------------------ */
/* TCP helpers                                                         */
/* ------------------------------------------------------------------ */

static int send_all(int fd, const void *data, size_t len)
{
    const unsigned char *p = data;
    size_t remaining = len;
    while (remaining > 0) {
        ssize_t n = send(fd, p, remaining, MSG_NOSIGNAL);
        if (n <= 0)
            return -1;
        p += n;
        remaining -= (size_t)n;
    }
    return 0;
}

static int recv_exact(int fd, void *buf, size_t len)
{
    unsigned char *p = buf;
    size_t remaining = len;
    while (remaining > 0) {
        ssize_t n = recv(fd, p, remaining, 0);
        if (n <= 0)
            return -1;
        p += n;
        remaining -= (size_t)n;
    }
    return 0;
}

static int send_message(int client_fd, uint32_t type, const void *payload,
                        uint32_t length)
{
    uint8_t header[HEADER_SIZE];
    /* Little-endian encoding */
    header[0] = (uint8_t)(type);
    header[1] = (uint8_t)(type >> 8);
    header[2] = (uint8_t)(type >> 16);
    header[3] = (uint8_t)(type >> 24);
    header[4] = (uint8_t)(length);
    header[5] = (uint8_t)(length >> 8);
    header[6] = (uint8_t)(length >> 16);
    header[7] = (uint8_t)(length >> 24);

    if (send_all(client_fd, header, HEADER_SIZE) < 0)
        return -1;
    if (length > 0 && send_all(client_fd, payload, length) < 0)
        return -1;
    return 0;
}

static int send_json_message(int client_fd, uint32_t type, const char *json)
{
    return send_message(client_fd, type, json, (uint32_t)strlen(json));
}

static int read_message(int client_fd, uint32_t *type, unsigned char **payload,
                        uint32_t *length)
{
    uint8_t header[HEADER_SIZE];
    if (recv_exact(client_fd, header, HEADER_SIZE) < 0)
        return -1;

    *type = (uint32_t)header[0]
          | ((uint32_t)header[1] << 8)
          | ((uint32_t)header[2] << 16)
          | ((uint32_t)header[3] << 24);
    *length = (uint32_t)header[4]
            | ((uint32_t)header[5] << 8)
            | ((uint32_t)header[6] << 16)
            | ((uint32_t)header[7] << 24);

    if (*length == 0) {
        *payload = NULL;
        return 0;
    }

    /* Sanity limit: 16 MB */
    if (*length > 16 * 1024 * 1024) {
        fprintf(stderr, "Message too large: %u bytes\n", *length);
        return -1;
    }

    *payload = malloc(*length);
    if (!*payload)
        return -1;

    if (recv_exact(client_fd, *payload, *length) < 0) {
        free(*payload);
        *payload = NULL;
        return -1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* JSON builders (no library — snprintf)                               */
/* ------------------------------------------------------------------ */

/* Escape a string for JSON (handles basic cases) */
static void json_escape(char *dst, size_t dst_len, const char *src)
{
    size_t di = 0;
    for (size_t si = 0; src[si] && di + 2 < dst_len; si++) {
        char c = src[si];
        if (c == '"' || c == '\\') {
            dst[di++] = '\\';
        }
        dst[di++] = c;
    }
    dst[di] = '\0';
}

static void build_hello_json(char *buf, size_t buflen)
{
    char escaped_model[256];
    json_escape(escaped_model, sizeof(escaped_model), camera_model);
    snprintf(buf, buflen,
        "{\"protocol_version\":1,"
        "\"backend\":\"linux-v4l2\","
        "\"backend_version\":\"0.1.0\","
        "\"camera_model\":\"%s\","
        "\"stream_format\":\"MJPEG\","
        "\"default_width\":%d,"
        "\"default_height\":%d,"
        "\"default_fps\":30}",
        escaped_model, CAPTURE_W, CAPTURE_H);
}

static void build_control_info_json(char *buf, size_t buflen)
{
    /* Re-read current values */
    int32_t exp_cur = exposure_range.cur;
    int32_t gain_cur = gain_range.cur;
    if (exposure_range.valid)
        v4l2_get_control(V4L2_CID_EXPOSURE_ABSOLUTE, &exp_cur);
    if (gain_range.valid)
        v4l2_get_control(V4L2_CID_GAIN, &gain_cur);

    /* Build controls array */
    char controls[1024] = "";
    int pos = 0;
    int first = 1;

    if (exposure_range.valid) {
        pos += snprintf(controls + pos, sizeof(controls) - (size_t)pos,
            "{\"id\":\"exposure\","
            "\"label\":\"Exposure\","
            "\"type\":\"int\","
            "\"min\":%d,\"max\":%d,\"step\":%d,\"cur\":%d,"
            "\"unit\":\"100us\"}",
            exposure_range.min, exposure_range.max,
            exposure_range.step, exp_cur);
        first = 0;
    }
    if (gain_range.valid) {
        if (!first)
            pos += snprintf(controls + pos, sizeof(controls) - (size_t)pos, ",");
        pos += snprintf(controls + pos, sizeof(controls) - (size_t)pos,
            "{\"id\":\"gain\","
            "\"label\":\"Gain\","
            "\"type\":\"int\","
            "\"min\":%d,\"max\":%d,\"step\":%d,\"cur\":%d,"
            "\"unit\":\"raw\"}",
            gain_range.min, gain_range.max,
            gain_range.step, gain_cur);
    }

    snprintf(buf, buflen, "{\"controls\":[%s]}", controls);
}

/* ------------------------------------------------------------------ */
/* JSON parsing (minimal — strstr + sscanf)                            */
/* ------------------------------------------------------------------ */

/* Parse SET_CONTROL: {"id":"exposure","value":250}
 * Writes control name into id_out and value into value_out.
 * Returns 0 on success. */
static int parse_set_control(const char *json, char *id_out, size_t id_len,
                             int32_t *value_out)
{
    /* Find "id" */
    const char *p = strstr(json, "\"id\"");
    if (!p) return -1;
    p = strchr(p + 4, '"');
    if (!p) return -1;
    p++; /* skip opening quote */
    const char *end = strchr(p, '"');
    if (!end) return -1;
    size_t len = (size_t)(end - p);
    if (len >= id_len) len = id_len - 1;
    memcpy(id_out, p, len);
    id_out[len] = '\0';

    /* Find "value" */
    p = strstr(json, "\"value\"");
    if (!p) return -1;
    p = strchr(p + 7, ':');
    if (!p) return -1;
    p++; /* skip colon */
    while (*p == ' ' || *p == '\t') p++;
    if (sscanf(p, "%d", value_out) != 1)
        return -1;

    return 0;
}

/* ------------------------------------------------------------------ */
/* Command handling                                                    */
/* ------------------------------------------------------------------ */

static void apply_set_control(const char *id, int32_t value)
{
    if (strcmp(id, "exposure") == 0) {
        v4l2_set_control(V4L2_CID_EXPOSURE_ABSOLUTE, value);
        fprintf(stderr, "Set exposure = %d\n", value);
    } else if (strcmp(id, "gain") == 0) {
        v4l2_set_control(V4L2_CID_GAIN, value);
        fprintf(stderr, "Set gain = %d\n", value);
    } else {
        fprintf(stderr, "Unknown control: %s\n", id);
    }
}

static void poll_commands(int client_fd)
{
    struct pollfd pfd;
    pfd.fd = client_fd;
    pfd.events = POLLIN;

    int ret = poll(&pfd, 1, 0);
    if (ret <= 0 || !(pfd.revents & POLLIN))
        return;

    uint32_t msg_type;
    unsigned char *payload = NULL;
    uint32_t length;

    if (read_message(client_fd, &msg_type, &payload, &length) < 0)
        return;

    if (msg_type == MSG_SET_CONTROL && payload) {
        /* Null-terminate for parsing */
        char *json = malloc(length + 1);
        if (json) {
            memcpy(json, payload, length);
            json[length] = '\0';

            char id[64];
            int32_t value;
            if (parse_set_control(json, id, sizeof(id), &value) == 0) {
                apply_set_control(id, value);
                char info[1024];
                build_control_info_json(info, sizeof(info));
                send_json_message(client_fd, MSG_CONTROL_INFO, info);
            }
            free(json);
        }
    } else if (msg_type == MSG_GET_CONTROLS) {
        char info[1024];
        build_control_info_json(info, sizeof(info));
        send_json_message(client_fd, MSG_CONTROL_INFO, info);
    } else {
        fprintf(stderr, "Ignoring message type 0x%02x\n", msg_type);
    }

    free(payload);
}

/* ------------------------------------------------------------------ */
/* Client handling                                                     */
/* ------------------------------------------------------------------ */

static void handle_client(int client_fd)
{
    /* Probe controls */
    probe_controls();

    /* Send HELLO */
    char hello[512];
    build_hello_json(hello, sizeof(hello));
    if (send_json_message(client_fd, MSG_HELLO, hello) < 0) {
        fprintf(stderr, "Failed to send HELLO\n");
        return;
    }

    /* Wait for client HELLO */
    uint32_t msg_type;
    unsigned char *payload = NULL;
    uint32_t length;
    if (read_message(client_fd, &msg_type, &payload, &length) < 0) {
        fprintf(stderr, "Failed to read client HELLO\n");
        free(payload);
        return;
    }
    if (msg_type != MSG_HELLO) {
        fprintf(stderr, "Expected HELLO from client, got 0x%02x\n", msg_type);
        free(payload);
        return;
    }
    free(payload);

    /* Send CONTROL_INFO */
    char info[1024];
    build_control_info_json(info, sizeof(info));
    if (send_json_message(client_fd, MSG_CONTROL_INFO, info) < 0) {
        fprintf(stderr, "Failed to send CONTROL_INFO\n");
        return;
    }

    /* Stream loop */
    while (!stop_flag) {
        /* Wait for camera frame readiness */
        struct pollfd cam_poll;
        cam_poll.fd = cam_fd;
        cam_poll.events = POLLIN;
        int pr = poll(&cam_poll, 1, 100);
        if (pr <= 0)
            continue;

        const unsigned char *frame_data;
        size_t frame_len;
        int is_allocated;
        int buf_index = capture_frame(&frame_data, &frame_len, &is_allocated);
        if (buf_index < 0)
            continue;

        if (send_message(client_fd, MSG_FRAME, frame_data, (uint32_t)frame_len) < 0) {
            if (is_allocated)
                free((void *)frame_data);
            else
                requeue_buffer(buf_index);
            fprintf(stderr, "Client disconnected (send failed)\n");
            return;
        }

        if (is_allocated)
            free((void *)frame_data);
        else
            requeue_buffer(buf_index);

        /* Poll for incoming commands between frames */
        poll_commands(client_fd);
    }
}

/* ------------------------------------------------------------------ */
/* Signal handler                                                      */
/* ------------------------------------------------------------------ */

static void signal_handler(int sig)
{
    (void)sig;
    stop_flag = 1;
}

/* ------------------------------------------------------------------ */
/* main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    /* Install signal handlers */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    /* Ignore SIGPIPE (handle send errors via return codes) */
    signal(SIGPIPE, SIG_IGN);

    /* Find camera device */
    char dev_path[288];
    if (find_device(dev_path, sizeof(dev_path)) < 0) {
        fprintf(stderr, "No V4L2 device found with VID=0x%04X PID=0x%04X. "
                "Check USB connection and that user is in 'video' group.\n",
                TARGET_VID, TARGET_PID);
        return 1;
    }

    /* Open and start capture */
    if (open_camera(dev_path) < 0) {
        fprintf(stderr, "Failed to open camera\n");
        return 1;
    }

    /* Disable auto-exposure for manual control */
    v4l2_set_control(V4L2_CID_EXPOSURE_AUTO, V4L2_EXPOSURE_MANUAL);

    /* Create TCP server */
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        close_camera();
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(SERVER_PORT);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(server_fd);
        close_camera();
        return 1;
    }

    if (listen(server_fd, 1) < 0) {
        perror("listen");
        close(server_fd);
        close_camera();
        return 1;
    }

    printf("Listening on 127.0.0.1:%d\n", SERVER_PORT);
    fflush(stdout);

    /* Accept one client */
    while (!stop_flag) {
        struct pollfd pfd;
        pfd.fd = server_fd;
        pfd.events = POLLIN;

        int ret = poll(&pfd, 1, 1000);
        if (ret <= 0)
            continue;

        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd, (struct sockaddr *)&client_addr,
                               &client_len);
        if (client_fd < 0) {
            if (errno == EINTR)
                continue;
            perror("accept");
            break;
        }

        fprintf(stderr, "Client connected from %s:%d\n",
                inet_ntoa(client_addr.sin_addr), ntohs(client_addr.sin_port));

        handle_client(client_fd);
        close(client_fd);
        break; /* Single client, exit after disconnect */
    }

    close(server_fd);
    close_camera();
    fprintf(stderr, "Camera server exiting\n");
    return 0;
}
