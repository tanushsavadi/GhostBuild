# Source text: led_breadboard__adafruit_leds

URL: https://learn.adafruit.com/adafruit-arduino-lesson-2-leds/leds
Fetched: 2026-10-17 (Pacific) by the knowledge lane with curl; HTML page text extracted by a script (not summarised); fetched from the ?view=all page.
Page: 'Arduino Lesson 2. LEDs' (Adafruit Learning System, last edited 2012-10-05). Kept: the 'LEDs' and 'Resistors' sections. The lesson itself uses an Arduino; only its LED and resistor facts are used.
Only the article body is kept below (site menus removed). Cites in knowledge/cards/ quote this file verbatim.

---

LEDs make great indicator lights. They use very little electricity and they pretty much last forever.
In this lession you will use perhaps the most common of all LEDs a 5mm red LED. 5Mm refers to the diameter of the LED and as well as 5mm, other common sizes are 3mm and the large fun 10mm LEDs.
You cannot directly connect an LED to a battery or voltage source. Firstly, because the LED has a positive and a negative lead and will not light if they are the wrong way around and secondly, an LED must be used with a resistor to limit or 'choke' the amount of current flowing through the LED - otherwise the LED could burn out!
If you do not use a resistor with an LED, then it may well be destroyed almost immediately, as too much current will flow through the LED, heating it and destroying the 'junction' where the light is produced.
There are two ways to tell which is the positive lead of the LED and which the negative.
Firstly, the positive lead is longer.
Secondly, where the negative lead enters the body of the LED, there is a flat edge to the case of the LED.
If you happen to have an LED that has a flat side next to the longer lead, you should assume that the longer lead is positive.
Resistors
As the name suggests, resistors resist the flow of electricity and the higher the value of the resistor, the more it resists and the less electrical current will flow through it. We are going to use this to control how much electricity flows through the LED and therefore how brightly it shines.
But first, a bit more about resistors.
The unit of resistance is called the Ohm, which is usually shortened to Ω the Greek letter Omega. Because an Ohm is a low value of resistance (it doesn't resist much at all), we also give the values of resistors in  kΩ (1000 Ω) and MΩ (1000,000 Ω). These are called kilo-ohms and mega-ohms.
In this lesson, we are going to use four different values of resistor, 270Ω, 470Ω, 2.2kΩ and 10kΩ. These resistors all look the same, except that they have different colored stripes on them. These stripes tell you the value of the resistor.
The resistor color code works like this, for resistors like this with three colored stripes and then a gold stripe at one end.
Each color has a number, as follows:
Black 0
Brown 1
Red 2
Orange 3
Yellow 4
Green 5
Blue 6
Purple 7
Gray 8
White 9
The first two striped are the first two digits of the value, so red, purple means 2, 7. The next stripe is the number of zeros that need to come after the first two digits, so if the third stripe is brown, as it is in the photograph above, then there will be one zero and so the resistor is 270Ω.
A resistor with stripes brown, black, orange is 10 and three zeros so 10,000 Ω in other words 10 kΩ.
Unlike LEDs, resistors do not have a positive and negative lead. They can be connected either way around.

