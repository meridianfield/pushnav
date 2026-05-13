---
title: Camera & Lens
---

## Sample Frame @ Bortle 8.5

**M45 (Pleiades), invisible to the naked eye from a Bortle 8.5 sky in Chennai, India.** The camera captures it clearly in a single short exposure. Naked-eye limiting magnitude here is around 2.3 mag; the camera reaches about 6.3 mag. Four magnitudes of improvement means roughly 40× more stars in the frame, plenty for a reliable plate-solve.

![Sample Frame](assets/single_frame_bortle8.png)

- Bortle 8.5 city sky (Chennai, India), under a hazy light-pollution dome.
- Naked-eye visual limiting magnitude here: around 2.3 mag.
- Sensor + F2.4 lens captures stars down to about 6.3 mag in this sky, with good plate-solve confidence.
- More than 40 stars detected per frame, well above the threshold for a reliable solve.
- Rule of thumb: each magnitude of fainter detection adds roughly 2.5× more stars in the frame, so 4 magnitudes ≈ 40× more visible stars.

## Quick Specs

```text
QUICK SPECS

Camera:       OV9281, 1MP mono, USB UVC
Lens:         M12, 25mm, F/2.4
FOV:          8.86° × 4.98°
Pixel scale:  24.9″/px
Plate-solve mag (Bortle 8.5):  ~6.3
Cost:         $41 USD (camera + lens)
```

## Supported Hardware

Currently support is provided only for this specific combination of camera and lens:

- **Camera**: [Waveshare OV9281 1MP Mono USB Camera](https://www.waveshare.com/ov9281-1mp-usb-camera-a.htm) [$26]
- **Lens**: [M12 Mount 25mm F2.4 Lens](https://www.seeedstudio.com/5MP-25mm-lens-p-5579.html) [$15]

These are reference suppliers. The **OV9281** module itself is widely sold by Arducam, Innomaker, AliExpress and others, and any M12 25mm F/2.4 lens with the correct mount works. If a link above goes dead, search the sensor name (`OV9281`) and lens specs and pick any reputable seller — the parts themselves are commodity.

## Why This Camera and Lens

- Off the shelf, affordable, and widely available
- For use in urban light polluted skies:
    - Mono sensor provides substantially better sensitivity and contrast for star detection compared to a color sensor
    - F2.4 aperture provides good light gathering power required to detect faint stars in light polluted urban skies
    - 25mm focal length in combination with the OV9281's 1/4" sensor size provides a ~8° field of view which is a good balance between having enough stars for reliable plate-solving and speed of solving
    - In my Bortle 8 city sky with a visual limiting magnitude of around 2.5, this camera/lens combo can reliably detect and plate-solve on stars down to about magnitude 6.5
- Standard USB (UVC) interface allows for cross-platform compatibility without needing custom drivers
- Calculated image scale and field of view (Astrometry results):
    - Size:	8.86° x 4.98° 
    - Radius: 5.081°
    - Pixel scale: 24.9 arcsec/pixel

>Currently only this specific camera and lens combination is supported. Support for additional cameras and lenses may be added in the future based on demand and usability. I decided to keep it this way for now to ensure a consistent and reliable user experience. Also this combination is very affordable and widely available, so it should be accessible for most users.

## Adding Support for More Cameras

- Adding the camera's VID/PID to the camera server's supported device list and implementing any necessary quirks for frame capture (if required)
- Generating the tetra3 star database for the new camera/lens's field of view and plate scale.
