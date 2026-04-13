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
 * camera_server.c — Windows DirectShow camera server
 *
 * Self-contained C implementation that captures MJPEG frames from the target
 * USB camera (VID 0x32E6, PID 0x9251) via DirectShow and serves them over
 * TCP using the same binary protocol as the macOS Swift and Linux V4L2
 * camera servers (see specs/start/SPEC_PROTOCOL_CAMERA.md).
 *
 * Build (from VS Developer Command Prompt):
 *   cl.exe /W4 /O2 /Fe:camera_server.exe camera_server.c ^
 *       ws2_32.lib ole32.lib oleaut32.lib strmiids.lib uuid.lib
 *
 * For YUYV fallback with libjpeg-turbo, also link jpeg.lib and add
 * the include/lib paths for your libjpeg-turbo installation.
 */

#define _CRT_SECURE_NO_WARNINGS
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <dshow.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Link libraries via pragmas so a simple cl.exe invocation works */
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")
#pragma comment(lib, "strmiids.lib")
#pragma comment(lib, "uuid.lib")

/* ------------------------------------------------------------------ */
/* ISampleGrabber definitions                                          */
/* ISampleGrabber was removed from modern Windows SDKs (qedit.h) but  */
/* the COM interface is still present in qedit.dll on all Windows     */
/* versions.  We define the minimal interface here.                    */
/* ------------------------------------------------------------------ */

/* {6B652FFF-11FE-4fce-92AD-0266B5D7C78F} */
static const GUID CLSID_SampleGrabber =
    {0xC1F400A0, 0x3F08, 0x11D3,
     {0x9F, 0x0B, 0x00, 0x60, 0x08, 0x03, 0x9E, 0x37}};

/* {6B652FFF-11FE-4fce-92AD-0266B5D7C78F} */
static const GUID IID_ISampleGrabber =
    {0x6B652FFF, 0x11FE, 0x4FCE,
     {0x92, 0xAD, 0x02, 0x66, 0xB5, 0xD7, 0xC7, 0x8F}};

/* {C1F400A4-3F08-11D3-9F0B-006008039E37} */
static const GUID CLSID_NullRenderer =
    {0xC1F400A4, 0x3F08, 0x11D3,
     {0x9F, 0x0B, 0x00, 0x60, 0x08, 0x03, 0x9E, 0x37}};

#undef INTERFACE
#define INTERFACE ISampleGrabber

DECLARE_INTERFACE_(ISampleGrabber, IUnknown) {
    /* IUnknown */
    STDMETHOD(QueryInterface)(THIS_ REFIID riid, void **ppv) PURE;
    STDMETHOD_(ULONG, AddRef)(THIS) PURE;
    STDMETHOD_(ULONG, Release)(THIS) PURE;
    /* ISampleGrabber */
    STDMETHOD(SetOneShot)(THIS_ BOOL oneShot) PURE;
    STDMETHOD(SetMediaType)(THIS_ const AM_MEDIA_TYPE *pType) PURE;
    STDMETHOD(GetConnectedMediaType)(THIS_ AM_MEDIA_TYPE *pType) PURE;
    STDMETHOD(SetBufferSamples)(THIS_ BOOL bufferThem) PURE;
    STDMETHOD(GetCurrentBuffer)(THIS_ long *pBufferSize, long *pBuffer) PURE;
    STDMETHOD(GetCurrentSample)(THIS_ void **ppSample) PURE;
    STDMETHOD(SetCallback)(THIS_ void *pCallback, long whichMethod) PURE;
};

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
#define SERVER_PORT  8764

/* ------------------------------------------------------------------ */
/* DirectShow state                                                    */
/* ------------------------------------------------------------------ */

static IGraphBuilder         *pGraph       = NULL;
static ICaptureGraphBuilder2 *pCapture     = NULL;
static IMediaControl         *pControl     = NULL;
static IBaseFilter           *pCamFilter   = NULL;
static IBaseFilter           *pGrabFilter  = NULL;
static IBaseFilter           *pNullFilter  = NULL;
static ISampleGrabber        *pGrabber     = NULL;
static IAMCameraControl      *pCamCtrl     = NULL;
static IAMVideoProcAmp       *pProcAmp     = NULL;

static int use_mjpeg = 1;

/* Camera model name */
static char camera_model[128] = "Unknown";

/* Control ranges */
typedef struct {
    int valid;
    long min, max, step, defval, cur;
    long flags;
} ctrl_range_t;

static ctrl_range_t exposure_range;
static ctrl_range_t gain_range;

/* Shutdown flag */
static volatile LONG stop_flag = 0;

/* ------------------------------------------------------------------ */
/* Utility: wide string to narrow (UTF-8)                              */
/* ------------------------------------------------------------------ */

static void wide_to_utf8(const WCHAR *src, char *dst, int dst_len)
{
    WideCharToMultiByte(CP_UTF8, 0, src, -1, dst, dst_len, NULL, NULL);
    dst[dst_len - 1] = '\0';
}

/* ------------------------------------------------------------------ */
/* Utility: case-insensitive substring search in wide string           */
/* ------------------------------------------------------------------ */

static const WCHAR *wcsistr(const WCHAR *haystack, const WCHAR *needle)
{
    if (!*needle) return haystack;
    for (; *haystack; haystack++) {
        const WCHAR *h = haystack, *n = needle;
        while (*h && *n && (towlower(*h) == towlower(*n))) {
            h++;
            n++;
        }
        if (!*n) return haystack;
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Device discovery via DirectShow enumeration                         */
/* ------------------------------------------------------------------ */

static HRESULT find_device(IBaseFilter **ppFilter)
{
    ICreateDevEnum *pSysDevEnum = NULL;
    IEnumMoniker *pEnumMoniker = NULL;
    IMoniker *pMoniker = NULL;
    HRESULT hr;

    hr = CoCreateInstance(&CLSID_SystemDeviceEnum, NULL, CLSCTX_INPROC_SERVER,
                          &IID_ICreateDevEnum, (void **)&pSysDevEnum);
    if (FAILED(hr)) return hr;

    hr = ICreateDevEnum_CreateClassEnumerator(pSysDevEnum,
             &CLSID_VideoInputDeviceCategory, &pEnumMoniker, 0);
    if (hr != S_OK) {
        ICreateDevEnum_Release(pSysDevEnum);
        return E_FAIL;
    }

    while (IEnumMoniker_Next(pEnumMoniker, 1, &pMoniker, NULL) == S_OK) {
        IPropertyBag *pPropBag = NULL;
        hr = IMoniker_BindToStorage(pMoniker, NULL, NULL,
                                    &IID_IPropertyBag, (void **)&pPropBag);
        if (SUCCEEDED(hr)) {
            VARIANT varPath;
            VariantInit(&varPath);

            /* Read DevicePath to match VID/PID */
            hr = IPropertyBag_Read(pPropBag, L"DevicePath", &varPath, NULL);
            if (SUCCEEDED(hr) && varPath.vt == VT_BSTR) {
                /* DevicePath contains something like:
                 * \\?\usb#vid_32e6&pid_9251#...
                 */
                WCHAR vid_str[16], pid_str[16];
                swprintf(vid_str, 16, L"vid_%04x", TARGET_VID);
                swprintf(pid_str, 16, L"pid_%04x", TARGET_PID);

                if (wcsistr(varPath.bstrVal, vid_str) &&
                    wcsistr(varPath.bstrVal, pid_str)) {
                    /* Match found — get friendly name */
                    VARIANT varName;
                    VariantInit(&varName);
                    hr = IPropertyBag_Read(pPropBag, L"FriendlyName",
                                           &varName, NULL);
                    if (SUCCEEDED(hr) && varName.vt == VT_BSTR) {
                        wide_to_utf8(varName.bstrVal, camera_model,
                                     sizeof(camera_model));
                    }
                    VariantClear(&varName);

                    /* Bind to filter */
                    hr = IMoniker_BindToObject(pMoniker, NULL, NULL,
                                               &IID_IBaseFilter,
                                               (void **)ppFilter);
                    VariantClear(&varPath);
                    IPropertyBag_Release(pPropBag);
                    IMoniker_Release(pMoniker);
                    IEnumMoniker_Release(pEnumMoniker);
                    ICreateDevEnum_Release(pSysDevEnum);

                    if (SUCCEEDED(hr)) {
                        fprintf(stderr, "Found camera '%s'\n", camera_model);
                        return S_OK;
                    }
                    return hr;
                }
            }
            VariantClear(&varPath);
            IPropertyBag_Release(pPropBag);
        }
        IMoniker_Release(pMoniker);
    }

    IEnumMoniker_Release(pEnumMoniker);
    ICreateDevEnum_Release(pSysDevEnum);
    return E_FAIL;
}

/* ------------------------------------------------------------------ */
/* Device discovery with retry                                         */
/* Some USB cameras take a few seconds to appear in DirectShow after   */
/* plug-in or system wake.  Retry for up to 8 seconds.                 */
/* ------------------------------------------------------------------ */

#define DEVICE_RETRY_TOTAL_MS   8000
#define DEVICE_RETRY_SLEEP_MS   500

static HRESULT find_device_with_retry(IBaseFilter **ppFilter)
{
    DWORD elapsed = 0;
    HRESULT hr;

    hr = find_device(ppFilter);
    if (SUCCEEDED(hr))
        return hr;

    fprintf(stderr,
            "Camera not found on first attempt, retrying for %d seconds...\n",
            DEVICE_RETRY_TOTAL_MS / 1000);

    while (elapsed < DEVICE_RETRY_TOTAL_MS) {
        Sleep(DEVICE_RETRY_SLEEP_MS);
        elapsed += DEVICE_RETRY_SLEEP_MS;

        hr = find_device(ppFilter);
        if (SUCCEEDED(hr))
            return hr;

        fprintf(stderr, "  retry at %lu ms - not found yet\n",
                (unsigned long)elapsed);
    }

    return E_FAIL;
}

/* ------------------------------------------------------------------ */
/* Capture graph setup                                                 */
/* ------------------------------------------------------------------ */

static void free_media_type(AM_MEDIA_TYPE *pmt)
{
    if (pmt->cbFormat != 0) {
        CoTaskMemFree(pmt->pbFormat);
        pmt->cbFormat = 0;
        pmt->pbFormat = NULL;
    }
    if (pmt->pUnk != NULL) {
        IUnknown_Release(pmt->pUnk);
        pmt->pUnk = NULL;
    }
}

static int try_format(IAMStreamConfig *pConfig, const GUID *pSubtype,
                      int width, int height)
{
    int count = 0, size = 0;
    HRESULT hr = IAMStreamConfig_GetNumberOfCapabilities(pConfig, &count, &size);
    if (FAILED(hr)) return 0;

    BYTE *pSCC = (BYTE *)malloc(size);
    if (!pSCC) return 0;

    for (int i = 0; i < count; i++) {
        AM_MEDIA_TYPE *pmt = NULL;
        hr = IAMStreamConfig_GetStreamCaps(pConfig, i, &pmt, pSCC);
        if (FAILED(hr) || !pmt) continue;

        if (IsEqualGUID(&pmt->subtype, pSubtype) &&
            !IsEqualGUID(&pmt->formattype, &GUID_NULL) &&
            IsEqualGUID(&pmt->formattype, &FORMAT_VideoInfo) &&
            pmt->cbFormat >= sizeof(VIDEOINFOHEADER)) {

            VIDEOINFOHEADER *pVIH = (VIDEOINFOHEADER *)pmt->pbFormat;
            if (pVIH->bmiHeader.biWidth == width &&
                abs(pVIH->bmiHeader.biHeight) == height) {

                hr = IAMStreamConfig_SetFormat(pConfig, pmt);
                free_media_type(pmt);
                CoTaskMemFree(pmt);
                free(pSCC);
                return SUCCEEDED(hr) ? 1 : 0;
            }
        }
        free_media_type(pmt);
        CoTaskMemFree(pmt);
    }

    free(pSCC);
    return 0;
}

static int open_camera(void)
{
    HRESULT hr;

    /* Create filter graph */
    hr = CoCreateInstance(&CLSID_FilterGraph, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IGraphBuilder, (void **)&pGraph);
    if (FAILED(hr)) { fprintf(stderr, "Failed to create FilterGraph\n"); return -1; }

    /* Create capture graph builder */
    hr = CoCreateInstance(&CLSID_CaptureGraphBuilder2, NULL, CLSCTX_INPROC_SERVER,
                          &IID_ICaptureGraphBuilder2, (void **)&pCapture);
    if (FAILED(hr)) { fprintf(stderr, "Failed to create CaptureGraphBuilder2\n"); return -1; }

    ICaptureGraphBuilder2_SetFiltergraph(pCapture, pGraph);

    /* Add camera filter to graph */
    hr = IGraphBuilder_AddFilter(pGraph, pCamFilter, L"Camera");
    if (FAILED(hr)) { fprintf(stderr, "Failed to add camera filter\n"); return -1; }

    /* Create sample grabber */
    hr = CoCreateInstance(&CLSID_SampleGrabber, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IBaseFilter, (void **)&pGrabFilter);
    if (FAILED(hr)) { fprintf(stderr, "Failed to create SampleGrabber\n"); return -1; }

    hr = IBaseFilter_QueryInterface(pGrabFilter, &IID_ISampleGrabber,
                                    (void **)&pGrabber);
    if (FAILED(hr)) { fprintf(stderr, "Failed to get ISampleGrabber\n"); return -1; }

    /* Get stream config from capture pin */
    IAMStreamConfig *pConfig = NULL;
    hr = ICaptureGraphBuilder2_FindInterface(pCapture, &PIN_CATEGORY_CAPTURE,
             &MEDIATYPE_Video, pCamFilter, &IID_IAMStreamConfig,
             (void **)&pConfig);

    /* Try MJPEG first, then YUYV */
    use_mjpeg = 1;
    if (pConfig) {
        if (try_format(pConfig, &MEDIASUBTYPE_MJPG, CAPTURE_W, CAPTURE_H)) {
            fprintf(stderr, "Using MJPEG capture %dx%d\n", CAPTURE_W, CAPTURE_H);
        } else if (try_format(pConfig, &MEDIASUBTYPE_YUY2, CAPTURE_W, CAPTURE_H)) {
            use_mjpeg = 0;
            fprintf(stderr, "MJPEG not available, using YUY2 capture %dx%d\n",
                    CAPTURE_W, CAPTURE_H);
        } else {
            fprintf(stderr, "Warning: Could not set preferred format, using default\n");
        }
        IAMStreamConfig_Release(pConfig);
    }

    /* Configure grabber media type */
    AM_MEDIA_TYPE mt;
    ZeroMemory(&mt, sizeof(mt));
    mt.majortype = MEDIATYPE_Video;
    mt.subtype = use_mjpeg ? MEDIASUBTYPE_MJPG : MEDIASUBTYPE_YUY2;
    pGrabber->lpVtbl->SetMediaType(pGrabber, &mt);
    pGrabber->lpVtbl->SetBufferSamples(pGrabber, TRUE);
    pGrabber->lpVtbl->SetOneShot(pGrabber, FALSE);

    /* Add grabber to graph */
    hr = IGraphBuilder_AddFilter(pGraph, pGrabFilter, L"Grabber");
    if (FAILED(hr)) { fprintf(stderr, "Failed to add grabber filter\n"); return -1; }

    /* Create and add null renderer (sink) */
    hr = CoCreateInstance(&CLSID_NullRenderer, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IBaseFilter, (void **)&pNullFilter);
    if (FAILED(hr)) { fprintf(stderr, "Failed to create NullRenderer\n"); return -1; }

    hr = IGraphBuilder_AddFilter(pGraph, pNullFilter, L"NullRenderer");
    if (FAILED(hr)) { fprintf(stderr, "Failed to add null renderer\n"); return -1; }

    /* Render the capture stream: Camera -> Grabber -> NullRenderer */
    hr = ICaptureGraphBuilder2_RenderStream(pCapture, &PIN_CATEGORY_CAPTURE,
             &MEDIATYPE_Video, (IUnknown *)pCamFilter, pGrabFilter, pNullFilter);
    if (FAILED(hr)) {
        fprintf(stderr, "Failed to render capture stream (hr=0x%08lx)\n", hr);
        return -1;
    }

    /* Get media control */
    hr = IGraphBuilder_QueryInterface(pGraph, &IID_IMediaControl,
                                      (void **)&pControl);
    if (FAILED(hr)) { fprintf(stderr, "Failed to get IMediaControl\n"); return -1; }

    /* Get camera control and video proc amp interfaces */
    hr = IBaseFilter_QueryInterface(pCamFilter, &IID_IAMCameraControl,
                                    (void **)&pCamCtrl);
    if (FAILED(hr)) {
        fprintf(stderr, "Warning: IAMCameraControl not available\n");
        pCamCtrl = NULL;
    }

    hr = IBaseFilter_QueryInterface(pCamFilter, &IID_IAMVideoProcAmp,
                                    (void **)&pProcAmp);
    if (FAILED(hr)) {
        fprintf(stderr, "Warning: IAMVideoProcAmp not available\n");
        pProcAmp = NULL;
    }

    /* Start the graph */
    hr = IMediaControl_Run(pControl);
    if (FAILED(hr)) {
        fprintf(stderr, "Failed to start capture (hr=0x%08lx)\n", hr);
        return -1;
    }

    fprintf(stderr, "Capture graph running\n");
    return 0;
}

/* ------------------------------------------------------------------ */
/* Capture cleanup                                                     */
/* ------------------------------------------------------------------ */

static void close_camera(void)
{
    if (pControl) { IMediaControl_Stop(pControl); IMediaControl_Release(pControl); pControl = NULL; }
    if (pProcAmp) { IAMVideoProcAmp_Release(pProcAmp); pProcAmp = NULL; }
    if (pCamCtrl) { IAMCameraControl_Release(pCamCtrl); pCamCtrl = NULL; }
    if (pGrabber) { pGrabber->lpVtbl->Release(pGrabber); pGrabber = NULL; }
    if (pNullFilter) { IGraphBuilder_RemoveFilter(pGraph, pNullFilter); IBaseFilter_Release(pNullFilter); pNullFilter = NULL; }
    if (pGrabFilter) { IGraphBuilder_RemoveFilter(pGraph, pGrabFilter); IBaseFilter_Release(pGrabFilter); pGrabFilter = NULL; }
    if (pCamFilter) { IGraphBuilder_RemoveFilter(pGraph, pCamFilter); IBaseFilter_Release(pCamFilter); pCamFilter = NULL; }
    if (pCapture) { ICaptureGraphBuilder2_Release(pCapture); pCapture = NULL; }
    if (pGraph) { IGraphBuilder_Release(pGraph); pGraph = NULL; }
}

/* ------------------------------------------------------------------ */
/* DirectShow controls                                                 */
/* ------------------------------------------------------------------ */

static void query_exposure(ctrl_range_t *out)
{
    memset(out, 0, sizeof(*out));
    if (!pCamCtrl) return;

    HRESULT hr = IAMCameraControl_GetRange(pCamCtrl,
        CameraControl_Exposure,
        &out->min, &out->max, &out->step, &out->defval, &out->flags);
    if (FAILED(hr)) { out->valid = 0; return; }
    out->valid = 1;

    long val, flags;
    hr = IAMCameraControl_Get(pCamCtrl, CameraControl_Exposure, &val, &flags);
    out->cur = SUCCEEDED(hr) ? val : out->defval;
}

static void query_gain(ctrl_range_t *out)
{
    memset(out, 0, sizeof(*out));
    if (!pProcAmp) return;

    HRESULT hr = IAMVideoProcAmp_GetRange(pProcAmp,
        VideoProcAmp_Gain,
        &out->min, &out->max, &out->step, &out->defval, &out->flags);
    if (FAILED(hr)) { out->valid = 0; return; }
    out->valid = 1;

    long val, flags;
    hr = IAMVideoProcAmp_Get(pProcAmp, VideoProcAmp_Gain, &val, &flags);
    out->cur = SUCCEEDED(hr) ? val : out->defval;
}

static void probe_controls(void)
{
    query_exposure(&exposure_range);
    query_gain(&gain_range);
    fprintf(stderr, "Exposure range: valid=%d min=%ld max=%ld step=%ld cur=%ld\n",
            exposure_range.valid, exposure_range.min, exposure_range.max,
            exposure_range.step, exposure_range.cur);
    fprintf(stderr, "Gain range: valid=%d min=%ld max=%ld step=%ld cur=%ld\n",
            gain_range.valid, gain_range.min, gain_range.max,
            gain_range.step, gain_range.cur);
}

static int set_exposure(long value)
{
    if (!pCamCtrl) return -1;
    return SUCCEEDED(IAMCameraControl_Set(pCamCtrl, CameraControl_Exposure,
                                          value, CameraControl_Flags_Manual)) ? 0 : -1;
}

static int set_gain(long value)
{
    if (!pProcAmp) return -1;
    return SUCCEEDED(IAMVideoProcAmp_Set(pProcAmp, VideoProcAmp_Gain,
                                         value, VideoProcAmp_Flags_Manual)) ? 0 : -1;
}

static void disable_auto_exposure(void)
{
    if (!pCamCtrl) return;
    long val, flags;
    HRESULT hr = IAMCameraControl_Get(pCamCtrl, CameraControl_Exposure,
                                       &val, &flags);
    if (SUCCEEDED(hr)) {
        IAMCameraControl_Set(pCamCtrl, CameraControl_Exposure,
                             val, CameraControl_Flags_Manual);
        fprintf(stderr, "Auto-exposure disabled (manual mode)\n");
    }
}

/* ------------------------------------------------------------------ */
/* YUYV → JPEG conversion (libjpeg-turbo)                              */
/* ------------------------------------------------------------------ */

#ifdef HAVE_LIBJPEG
#include <jpeglib.h>

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

    unsigned char *row = (unsigned char *)malloc(CAPTURE_W * 3);
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
#endif /* HAVE_LIBJPEG */

/* ------------------------------------------------------------------ */
/* Frame capture                                                       */
/* ------------------------------------------------------------------ */

/* Duplicate frame detection state.
 * ISampleGrabber::GetCurrentBuffer is a polling API — it returns the
 * same buffer until DirectShow delivers a new frame.  Without this
 * check the server would flood the TCP connection with duplicate data,
 * causing high CPU usage and starving the Python UI of update time.
 * We compare frame size + a fast checksum of the first 64 bytes.
 */
static long  prev_frame_size = 0;
static DWORD prev_frame_hash = 0;

static DWORD quick_hash(const unsigned char *data, long len)
{
    DWORD h = 0x811c9dc5u;  /* FNV-1a offset basis */
    long n = len < 64 ? len : 64;
    for (long i = 0; i < n; i++) {
        h ^= data[i];
        h *= 0x01000193u;   /* FNV-1a prime */
    }
    return h;
}

/* Get the current frame from the sample grabber.
 * For MJPEG: raw JPEG data from the grabber buffer.
 * For YUYV:  convert to JPEG (requires HAVE_LIBJPEG).
 * Returns 0 on success, -1 on failure (includes duplicate detection).
 * Caller must free(*out_data) when done.
 */
static int capture_frame(unsigned char **out_data, long *out_len)
{
    long buf_size = 0;
    HRESULT hr;

    /* First call to get buffer size */
    hr = pGrabber->lpVtbl->GetCurrentBuffer(pGrabber, &buf_size, NULL);
    if (FAILED(hr) || buf_size <= 0)
        return -1;

    unsigned char *buf = (unsigned char *)malloc(buf_size);
    if (!buf) return -1;

    hr = pGrabber->lpVtbl->GetCurrentBuffer(pGrabber, &buf_size, (long *)buf);
    if (FAILED(hr)) {
        free(buf);
        return -1;
    }

    /* Duplicate frame detection — skip if same as previous */
    DWORD h = quick_hash(buf, buf_size);
    if (buf_size == prev_frame_size && h == prev_frame_hash) {
        free(buf);
        return -1;  /* same frame, caller will sleep */
    }
    prev_frame_size = buf_size;
    prev_frame_hash = h;

    if (use_mjpeg) {
        *out_data = buf;
        *out_len = buf_size;
        return 0;
    }

#ifdef HAVE_LIBJPEG
    /* YUYV → JPEG */
    unsigned char *jpeg_data = NULL;
    unsigned long jpeg_len = 0;
    if (yuyv_to_jpeg(buf, (size_t)buf_size, &jpeg_data, &jpeg_len) < 0) {
        free(buf);
        return -1;
    }
    free(buf);
    *out_data = jpeg_data;
    *out_len = (long)jpeg_len;
    return 0;
#else
    /* No libjpeg — cannot convert YUYV */
    fprintf(stderr, "YUYV capture but no libjpeg support compiled in\n");
    free(buf);
    return -1;
#endif
}

/* ------------------------------------------------------------------ */
/* TCP helpers (Winsock2)                                               */
/* ------------------------------------------------------------------ */

static int send_all(SOCKET fd, const void *data, int len)
{
    const char *p = (const char *)data;
    int remaining = len;
    while (remaining > 0) {
        int n = send(fd, p, remaining, 0);
        if (n == SOCKET_ERROR || n == 0)
            return -1;
        p += n;
        remaining -= n;
    }
    return 0;
}

static int recv_exact(SOCKET fd, void *buf, int len)
{
    char *p = (char *)buf;
    int remaining = len;
    while (remaining > 0) {
        int n = recv(fd, p, remaining, 0);
        if (n == SOCKET_ERROR || n == 0)
            return -1;
        p += n;
        remaining -= n;
    }
    return 0;
}

static int send_message(SOCKET client_fd, uint32_t type, const void *payload,
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
    if (length > 0 && send_all(client_fd, payload, (int)length) < 0)
        return -1;
    return 0;
}

static int send_json_message(SOCKET client_fd, uint32_t type, const char *json)
{
    return send_message(client_fd, type, json, (uint32_t)strlen(json));
}

static int read_message(SOCKET client_fd, uint32_t *type, unsigned char **payload,
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

    *payload = (unsigned char *)malloc(*length);
    if (!*payload)
        return -1;

    if (recv_exact(client_fd, *payload, (int)*length) < 0) {
        free(*payload);
        *payload = NULL;
        return -1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* JSON builders (no library — snprintf)                               */
/* ------------------------------------------------------------------ */

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
        "\"backend\":\"windows-directshow\","
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
    long exp_cur = exposure_range.cur;
    long gain_cur = gain_range.cur;
    if (exposure_range.valid && pCamCtrl) {
        long val, flags;
        if (SUCCEEDED(IAMCameraControl_Get(pCamCtrl, CameraControl_Exposure,
                                           &val, &flags)))
            exp_cur = val;
    }
    if (gain_range.valid && pProcAmp) {
        long val, flags;
        if (SUCCEEDED(IAMVideoProcAmp_Get(pProcAmp, VideoProcAmp_Gain,
                                          &val, &flags)))
            gain_cur = val;
    }

    char controls[1024] = "";
    int pos = 0;
    int first = 1;

    if (exposure_range.valid) {
        pos += snprintf(controls + pos, sizeof(controls) - (size_t)pos,
            "{\"id\":\"exposure\","
            "\"label\":\"Exposure\","
            "\"type\":\"int\","
            "\"min\":%ld,\"max\":%ld,\"step\":%ld,\"cur\":%ld,"
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
            "\"min\":%ld,\"max\":%ld,\"step\":%ld,\"cur\":%ld,"
            "\"unit\":\"raw\"}",
            gain_range.min, gain_range.max,
            gain_range.step, gain_cur);
    }

    snprintf(buf, buflen, "{\"controls\":[%s]}", controls);
}

/* ------------------------------------------------------------------ */
/* JSON parsing (minimal — strstr + sscanf)                            */
/* ------------------------------------------------------------------ */

static int parse_set_control(const char *json, char *id_out, size_t id_len,
                             long *value_out)
{
    const char *p = strstr(json, "\"id\"");
    if (!p) return -1;
    p = strchr(p + 4, '"');
    if (!p) return -1;
    p++;
    const char *end = strchr(p, '"');
    if (!end) return -1;
    size_t len = (size_t)(end - p);
    if (len >= id_len) len = id_len - 1;
    memcpy(id_out, p, len);
    id_out[len] = '\0';

    p = strstr(json, "\"value\"");
    if (!p) return -1;
    p = strchr(p + 7, ':');
    if (!p) return -1;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (sscanf(p, "%ld", value_out) != 1)
        return -1;

    return 0;
}

/* ------------------------------------------------------------------ */
/* Command handling                                                    */
/* ------------------------------------------------------------------ */

static void apply_set_control(const char *id, long value)
{
    if (strcmp(id, "exposure") == 0) {
        set_exposure(value);
        fprintf(stderr, "Set exposure = %ld\n", value);
    } else if (strcmp(id, "gain") == 0) {
        set_gain(value);
        fprintf(stderr, "Set gain = %ld\n", value);
    } else {
        fprintf(stderr, "Unknown control: %s\n", id);
    }
}

static void poll_commands(SOCKET client_fd)
{
    fd_set readfds;
    struct timeval tv;
    FD_ZERO(&readfds);
    FD_SET(client_fd, &readfds);
    tv.tv_sec = 0;
    tv.tv_usec = 0;

    int ret = select(0, &readfds, NULL, NULL, &tv);
    if (ret <= 0 || !FD_ISSET(client_fd, &readfds))
        return;

    uint32_t msg_type;
    unsigned char *payload = NULL;
    uint32_t length;

    if (read_message(client_fd, &msg_type, &payload, &length) < 0)
        return;

    if (msg_type == MSG_SET_CONTROL && payload) {
        char *json = (char *)malloc(length + 1);
        if (json) {
            memcpy(json, payload, length);
            json[length] = '\0';

            char id[64];
            long value;
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

static void handle_client(SOCKET client_fd)
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
    while (!InterlockedCompareExchange(&stop_flag, 0, 0)) {
        unsigned char *frame_data = NULL;
        long frame_len = 0;

        if (capture_frame(&frame_data, &frame_len) < 0) {
            /* No frame ready yet — small sleep to avoid busy-waiting */
            Sleep(5);
            continue;
        }

        if (send_message(client_fd, MSG_FRAME, frame_data,
                         (uint32_t)frame_len) < 0) {
            free(frame_data);
            fprintf(stderr, "Client disconnected (send failed)\n");
            return;
        }

        free(frame_data);

        /* Poll for incoming commands between frames */
        poll_commands(client_fd);
    }
}

/* ------------------------------------------------------------------ */
/* Console control handler (replaces Unix signal handlers)             */
/* ------------------------------------------------------------------ */

static BOOL WINAPI console_handler(DWORD dwCtrlType)
{
    switch (dwCtrlType) {
    case CTRL_C_EVENT:
    case CTRL_CLOSE_EVENT:
    case CTRL_BREAK_EVENT:
        InterlockedExchange(&stop_flag, 1);
        return TRUE;
    default:
        return FALSE;
    }
}

/* ------------------------------------------------------------------ */
/* main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    /* Install console control handler */
    SetConsoleCtrlHandler(console_handler, TRUE);

    /* Initialize Winsock */
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed\n");
        return 1;
    }

    /* Initialize COM */
    HRESULT hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (FAILED(hr)) {
        fprintf(stderr, "CoInitializeEx failed (hr=0x%08lx)\n", hr);
        WSACleanup();
        return 1;
    }

    /* Find camera device (retries for up to 8s if not found immediately) */
    hr = find_device_with_retry(&pCamFilter);
    if (FAILED(hr) || pCamFilter == NULL) {
        fprintf(stderr,
                "No video device found with VID=0x%04X PID=0x%04X.\n"
                "Check USB connection and that the camera is recognized by Windows.\n",
                TARGET_VID, TARGET_PID);
        CoUninitialize();
        WSACleanup();
        return 1;
    }

    /* Open and start capture */
    if (open_camera() < 0) {
        fprintf(stderr, "Failed to open camera\n");
        close_camera();
        CoUninitialize();
        WSACleanup();
        return 1;
    }

    /* Disable auto-exposure for manual control */
    disable_auto_exposure();

    /* Create TCP server */
    SOCKET server_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server_fd == INVALID_SOCKET) {
        fprintf(stderr, "socket() failed: %d\n", WSAGetLastError());
        close_camera();
        CoUninitialize();
        WSACleanup();
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, (const char *)&opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(SERVER_PORT);

    /* Bind with retry — port may be in TIME_WAIT from a previous run */
    {
        int bind_attempts = 0;
        const int MAX_BIND_ATTEMPTS = 10;
        const int BIND_RETRY_MS = 500;

        while (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) == SOCKET_ERROR) {
            int err = WSAGetLastError();
            bind_attempts++;
            if (bind_attempts >= MAX_BIND_ATTEMPTS) {
                fprintf(stderr, "bind() failed after %d attempts: %d\n",
                        bind_attempts, err);
                closesocket(server_fd);
                close_camera();
                CoUninitialize();
                WSACleanup();
                return 1;
            }
            fprintf(stderr, "bind() failed (err=%d), retrying in %dms (%d/%d)\n",
                    err, BIND_RETRY_MS, bind_attempts, MAX_BIND_ATTEMPTS);
            Sleep(BIND_RETRY_MS);
        }
    }

    if (listen(server_fd, 1) == SOCKET_ERROR) {
        fprintf(stderr, "listen() failed: %d\n", WSAGetLastError());
        closesocket(server_fd);
        close_camera();
        CoUninitialize();
        WSACleanup();
        return 1;
    }

    printf("Listening on 127.0.0.1:%d\n", SERVER_PORT);
    fflush(stdout);

    /* Accept one client */
    while (!InterlockedCompareExchange(&stop_flag, 0, 0)) {
        fd_set readfds;
        struct timeval tv;
        FD_ZERO(&readfds);
        FD_SET(server_fd, &readfds);
        tv.tv_sec = 1;
        tv.tv_usec = 0;

        int ret = select(0, &readfds, NULL, NULL, &tv);
        if (ret <= 0)
            continue;

        struct sockaddr_in client_addr;
        int client_len = sizeof(client_addr);
        SOCKET client_fd = accept(server_fd, (struct sockaddr *)&client_addr,
                                  &client_len);
        if (client_fd == INVALID_SOCKET) {
            fprintf(stderr, "accept() failed: %d\n", WSAGetLastError());
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
        fprintf(stderr, "Client connected from %s:%d\n",
                client_ip, ntohs(client_addr.sin_port));

        handle_client(client_fd);
        closesocket(client_fd);
        break; /* Single client, exit after disconnect */
    }

    closesocket(server_fd);
    close_camera();
    CoUninitialize();
    WSACleanup();
    fprintf(stderr, "Camera server exiting\n");
    return 0;
}
