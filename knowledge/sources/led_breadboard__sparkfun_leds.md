# Source text: led_breadboard__sparkfun_leds

URL: https://learn.sparkfun.com/tutorials/light-emitting-diodes-leds
Fetched: 2026-10-17 (Pacific) by the knowledge lane with curl; HTML page text extracted by a script (not summarised); fetched from the ?print=1 /all view. CC BY-SA 3.0, SparkFun Electronics.
Page: 'Light-Emitting Diodes (LEDs)'. Kept: sections 'How to Use Them' and 'LEDs Without Math'.
Only the article body is kept below (site menus, comments and ads removed). Cites in knowledge/cards/ quote this file verbatim.

---

How to Use Them
So you've come to the sensible conclusion that you need to put LEDs on everything. We thought you'd come around.
Let's go over the rule book:
1) Polarity Matters
In electronics, polarity indicates whether a circuit component is symmetric or not. LEDs, being diodes, will only allow current to flow in one direction. And when there's no current-flow, there's no light. Luckily, this also means that you can't break an LED by plugging it in backwards. Rather, it just won't work.
The positive side of the LED is called the "anode" and is marked by having a longer "lead," or leg. The other, negative side of the LED is called the "cathode." Current flows from the anode to the cathode and never the opposite direction. A reversed LED can keep an entire circuit from operating properly by blocking current flow. So don't freak out if adding an LED breaks your circuit. Try flipping it around.
2) Moar Current Equals Moar Light
The brightness of an LED is directly dependent on how much current it draws. That means two things. The first being that super bright LEDs drain batteries more quickly, because the extra brightness comes from the extra power being used. The second is that you can control the brightness of an LED by controlling the amount of current through it. But, setting the mood isn't the only reason to cut back your current.
3) There is Such a Thing as Too Much Power
If you connect an LED directly to a current source it will try to dissipate as much power as it's allowed to draw, and, like the tragic heroes of olde, it will destroy itself. That's why it's important to limit the amount of current flowing across the LED.
For this, we employ resistors. Resistors limit the flow of electrons in the circuit and protect the LED from trying to draw too much current. Don't worry, it only takes a little basic math to determine the best resistor value to use. You can find out all about it in the example applications of our resistor tutorial!
Resistors
April 1, 2013
A tutorial on all things resistors. What is a resistor, how do they behave in parallel/series, decoding the resistor color codes, and resistor applications.
Don't let all of this math scare you, it's actually pretty hard to mess things up too badly. In the next section, we'll go over how to make an LED circuit without getting your calculator.
LEDs Without Math
Before we talk about how to read a datasheet, let's hook up some LEDs. After all, this is an LED tutorial, not a reading tutorial.
It's also not a math tutorial, so we'll give you a few rules of thumb for getting LEDs up and running. As you've probably put together from the info in the last section, you'll need a battery, a resistor, and an LED. We're using a battery as our power source, because they're easy to find and they can't supply a dangerous amount of current.
The basic template for an LED circuit is pretty simple, just connect your battery, resistor and LED in series. Like this:
330 Ohm Resistor
A good resistor value for most LEDs is 330 Ohms ( orange  -  orange  -  brown ). You can use the information from the last section to help you determine the exact value you need, but this is LEDs without math... So, start by popping a 330 Ohm resistor into the above circuit and see what happens.
Trial and Error
The interesting thing about resistors is that they'll dissipate extra power as heat, so if you have a resistor that's getting warm, you probably need to go with a smaller resistance. If your resistor is too small, however, you run the risk of burning out the LED! Given that you have a handful of LEDs and resistors to play with, here's a flow chart to help you design your LED circuit by trial and error:
Throwies with a Coin Cell Battery
Another way to light up an LED is to just connect it to a coin cell battery! Since the coin cell can't source enough current to damage the LED, you can connect them directly together! Just push a CR2032 coin cell between the leads of the LED. The long leg of the LED should be touching the side of the battery marked with a "+". Now you can wrap some tape around the whole thing, add a magnet, and stick it to stuff! Yay for throwies!
Of course, if you're not getting great results with the trial and error approach, you can always get out your calculator and math it up. Don't worry, it's not hard to calculate the best resistor value for your circuit. But before you can figure out the optimal resistor value, you'll need to find the optimal current for your LED. For that we'll need to report to the datasheet...
