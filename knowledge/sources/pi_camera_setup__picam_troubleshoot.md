# Source text: pi_camera_setup__picam_troubleshoot

URL: https://www.raspberrypi.com/documentation/computers/camera_software.html
Fetched: 2026-10-17 (Pacific) by the knowledge lane. Text is the raw AsciiDoc source of that official page, taken byte-exact from the official docs repository
https://github.com/raspberrypi/documentation (branch master, commit ddea98e98dafe9419feb4fd82710c2fbdef7dc44), file documentation/asciidoc/computers/camera/troubleshooting.adoc
(CC BY-SA 4.0). It was fetched this way because www.raspberrypi.com returns HTTP 403 to curl. The rendered page was also opened with WebFetch
(model-summarised) only to confirm the page and section headings exist. AsciiDoc markup (xref:, +, *, ==) is part of the text below, so cite
only sentences that do not span markup.
Page: Troubleshooting (computers/camera_software)

---

== Troubleshooting

If your Camera Module doesn't work like you expect, try some of the following fixes:

* On Raspberry Pi 3 and earlier, the graphics hardware can only support images up to 2048×2048 pixels, which places a limit on the camera images that can be resized into the preview window. As a result, video encoding of images larger than 2048 pixels wide produces corrupted or missing preview images.
* On Raspberry Pi 4, the graphics hardware can only support images up to 4096×4096 pixels, which places a limit on the camera images that can be resized into the preview window. As a result, video encoding of images larger than 4096 pixels wide produces corrupted or missing preview images.
* The preview window might show display tearing in a desktop environment. This is a known, unfixable issue.
* Check that the FFC (Flat Flexible Cable) is firmly seated, fully inserted, and that the contacts face the correct direction. The FFC should be evenly inserted, not angled.
* If you use a connector between the camera and your Raspberry Pi, check that the ports on the connector are firmly seated, fully inserted, and that the contacts face the correct direction.
* Check to make sure that the FFC (Flat Flexible Cable) is attached to the CSI (Camera Serial Interface), _not_ the DSI (Display Serial Interface). The connector fits into either port, but only the CSI port powers and controls the camera. Look for the `CSI` label printed on the board near the port.
* xref:os.adoc#update-software[Update to the latest software.]
* Try a different power supply. The Camera Module adds about 200-250mA to the power requirements of your Raspberry Pi. If your power supply is low quality, your Raspberry Pi might not be able to power the Camera module.
* If you've checked all the above issues and your Camera Module still doesn't work like you expect, try posting on our forums for more help.
