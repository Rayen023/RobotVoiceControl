# KUKA KR 50 R2100

## Technical Data

* **Maximum reach:** 2101 mm
* **Rated payload:** 50 kg
* **Maximum payload:** 61 kg
* **Maximum supplementary load, rotating column / link arm / arm:** Not specified in the provided text.
* **Pose repeatability (ISO 9283):** $\pm$ 0.05 mm
* **Number of axes:** 6
* **Mounting position:** Floor, Ceiling, Wall, Desired angle
* **Footprint:** 603 mm x 480 mm
* **Weight:** approx. 533 kg

## Axis Data

| Axis | Motion Range        | Speed with Rated Payload |
| :--- | :------------------ | :----------------------- |
| A1   | $\pm185^{\circ}$               | $180 ^{\circ}/s$                  |
| A2   | $-175^{\circ} / 60^{\circ}$         | $175 ^{\circ}/s$                  |
| A3   | $-120^{\circ} / 165^{\circ}$        | $175 ^{\circ}/s$                  |
| A4   | $\pm180^{\circ}$               | $250 ^{\circ}/s$                  |
| A5   | $\pm125^{\circ}$               | $250 ^{\circ}/s$                  |
| A6   | $\pm350^{\circ}$               | $360 ^{\circ}/s$                  |

## Operating Conditions

* **Ambient temperature during operation:** $0 ^{\circ}C$ to $55 ^{\circ}C$ (273 K to 328 K)

## Protection Rating

| Item                                | Rating (IEC 60529) |
| :---------------------------------- | :----------------- |
| Protection rating                   | IP65               |
| Schutzart Arm (Protection rating Arm) | IP65 / IP67        |
| Protection rating, robot wrist      | IP65 / IP67        |

## Controller

* KR C5; KR C4

## Certificates

* **ESD requirements:** IEC61340-5-1; ANSI/ESD S20.20

## Payload Diagram Notes

The KR 50 R2100 is designed for a rated payload of 50 kg in order to optimize the dynamic performance of the robot. The maximum payload of 61 kg applies only if the position of the center of mass is 0 mm and a supplementary load optimized for the load case is mounted. The specific load case must be verified using KUKA.Load or KUKA Compose. For further consultation, please contact KUKA Support.

## Workspace Graphic (Figure 1)

This diagram illustrates the robot's range of motion. All dimensions are in mm.
* **Key Linear Dimensions:**
    * Horizontal reach components: 1035, 185, 991, 175, 1595
    * Overall horizontal reach: 1748, 2101
    * Vertical reach components: 50, 890, 575, 384
    * Overall vertical reach from base: 2501
    * Total height including base: 3733
* **Key Angular Limits Shown:**
    * Axis 2 (approx.): $-175^{\circ}$ (backward tilt of main arm) / $+60^{\circ}$ (forward tilt of main arm)
    * Axis 3 (approx.): $-120^{\circ}$ (arm bending down) / $+165^{\circ}$ (arm bending up relative to Axis 2 link)

## Payload Diagram (Figure 2)

This diagram shows the relationship between the load capacity (in kg) and the position of the center of mass (Lxy and Lz in mm).
* **Axes:**
    * Lxy (horizontal distance from A-axis to center of mass): Ranges from 0 to approx. 700 mm.
    * Lz (vertical distance from flange to center of mass): Ranges from 0 to 1000 mm.
* **Load Capacities:**
    * **20 kg:** Permissible up to Lxy $\approx$ 650 mm (at lower Lz), with Lz extending up to $\approx$ 700 mm (at lower Lxy). The boundary slopes downwards from (Lxy $\approx$ 0, Lz $\approx$ 700) to (Lxy $\approx$ 650, Lz $\approx$ 650) and then sharply down.
    * **25 kg:** Permissible up to Lxy $\approx$ 520 mm, with Lz extending up to $\approx$ 500 mm.
    * **30 kg:** Permissible up to Lxy $\approx$ 430 mm, with Lz extending up to $\approx$ 400 mm.
    * **35 kg:** Permissible up to Lxy $\approx$ 370 mm, with Lz extending up to $\approx$ 350 mm.
    * **40 kg:** Permissible up to Lxy $\approx$ 300 mm, with Lz extending up to $\approx$ 300 mm.
    * **45 kg:** Permissible up to Lxy $\approx$ 280 mm, with Lz extending up to $\approx$ 250 mm.
    * **50 kg (Rated Payload):** Permissible up to Lxy $\approx$ 200 mm, with Lz extending up to $\approx$ 200 mm.
    * **61 kg (Maximum Payload):** Indicated at Lz close to 0 mm and Lxy $\approx$ 100 mm.

## Mounting Flange (Figure 3)

This diagram provides dimensions for the robot's mounting flange. All dimensions are in mm unless otherwise specified.
* **Overall View:**
    * Circular flange with an approximate outer diameter of $\emptyset300$ (from the right-side view).
* **Hole Pattern & Central Features (Left View - Top Down):**
    * **Outer Bolt Circle Diameter (PCD):** $\emptyset100$.
    * **Mounting Holes:** 9x M8 threaded holes ($\emptyset9 \times 6.2$ clearance holes shown, indicating 9 holes of 6.2mm diameter for M8 bolts). These are shown spaced at $30^{\circ}$ intervals in some parts of the diagram, but 9 holes would typically be $40^{\circ}$ apart. The "M8 (9x)" is the primary specification.
    * **Central Bore / Recess Diameters:**
        * $\emptyset129$ (largest diameter of a recess/feature)
        * $\emptyset125^{h8}$ (precision bore)
        * $\emptyset122\pm0.1$ (another recess diameter)
        * $\emptyset63^{H7}$ (central precision bore/spigot)
    * **Dowel Pin Hole(s):** $\emptyset8^{H7}$ with a depth (t) of 6.2 mm. One is explicitly shown.
* **Section J-J (Cross-Sectional View):**
    * **Total height of flange section shown:** 20 mm.
    * **Depth of largest recess ($\emptyset129$):** 9.2 mm from the top surface.
    * **Height of a small step/lip:** 3 mm.
    * **Another internal height dimension:** 8.5 mm.