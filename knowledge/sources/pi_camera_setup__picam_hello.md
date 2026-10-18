# Source text: pi_camera_setup__picam_hello

URL: https://www.raspberrypi.com/documentation/computers/camera_software.html
Fetched: 2026-10-17 (Pacific) by the knowledge lane. Text is the raw AsciiDoc source of that official page, taken byte-exact from the official docs repository
https://github.com/raspberrypi/documentation (branch master, commit ddea98e98dafe9419feb4fd82710c2fbdef7dc44), file documentation/asciidoc/computers/camera/rpicam_hello.adoc
(CC BY-SA 4.0). It was fetched this way because www.raspberrypi.com returns HTTP 403 to curl. The rendered page was also opened with WebFetch
(model-summarised) only to confirm the page and section headings exist. AsciiDoc markup (xref:, +, *, ==) is part of the text below, so cite
only sentences that do not span markup.
Page: rpicam-hello (computers/camera_software)

---

=== `rpicam-hello`

`rpicam-hello` briefly displays a preview window containing the video feed from a connected camera. To use `rpicam-hello` to display a preview window for five seconds, run the following command in a terminal:

[source,console]
----
$ rpicam-hello
----

You can pass an optional duration (in milliseconds) with the xref:camera_software.adoc#timeout[`timeout`] option. A value of `0` runs the preview indefinitely:

[source,console]
----
$ rpicam-hello --timeout 0
----

Use `Ctrl+C` in the terminal or the close button on the preview window to stop `rpicam-hello`.

==== Display an image sensor preview

Most of the `rpicam-apps` display a preview image in a window. If there is no active desktop environment, the preview draws directly to the display using the Linux Direct Rendering Manager (DRM). Otherwise, `rpicam-apps` attempt to use the desktop environment. Both paths use zero-copy GPU buffer sharing: as a result, X forwarding is _not_ supported.

If you run the X window server and want to use X forwarding, pass the xref:camera_software.adoc#qt-preview[`qt-preview`] flag to render the preview window in a https://en.wikipedia.org/wiki/Qt_(software)[Qt] window. The Qt preview window uses more resources than the alternatives.

NOTE: Older systems using Gtk2 might, when linked with OpenCV, produce `Glib-GObject` errors and fail to show the Qt preview window. In this case edit the file `/etc/xdg/qt5ct/qt5ct.conf` as root and replace the line containing `style=gtk2` with `style=gtk3`.

To suppress the preview window entirely, pass the xref:camera_software.adoc#nopreview[`nopreview`] flag:

[source,console]
----
$ rpicam-hello -n
----

The xref:camera_software.adoc#info-text[`info-text`] option displays image information on the window title bar using `%` directives. For example, the following command displays the current red and blue gain values:

[source,console]
----
$ rpicam-hello --info-text "red gain %rg, blue gain %bg"
----

For a full list of directives, see the xref:camera_software.adoc#info-text[`info-text` reference].
