## Firmware Compilation & Flashing
The firmware source code is located in the `/VirtualSerial` directory, with the main logic written in the `VirtualSerial.c` file. 

**Important:** Before compiling, you must extract the LUFA library by unzipping the `lufa-master.zip` file included in the directory.

* **Compile:** 1. Open the **QMK MSYS** terminal.
  2. Navigate to the source folder by typing: `cd path/to/VirtualSerial`
  3. Compile the code by typing the command: `make`
* **Flashing:** The generated `.hex` file was then uploaded to the ATmega32U4 microcontroller using the **QMK Toolbox** interface.
