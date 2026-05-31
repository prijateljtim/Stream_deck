# Custom Macro Pad & Hive Center App

## About the Project
This is an open-source, cost-effective, and highly customizable macro pad designed as an alternative to commercial solutions like the Elgato Stream Deck. The project covers the entire development lifecycle: custom PCB design, a 3D-printed enclosure, C firmware, and a dedicated Python desktop application called **Hive Center**.

## Features
* **Plug-and-Play:** The background application automatically detects the connected device via a serial (USB) connection.
* **Intuitive GUI:** Configure keys and functions easily through the custom Hive Center interface.
* **Drag & Drop App Launcher:** Quickly assign actions by dragging any installed app or game directly onto a virtual key.
* **Custom Macros:** Record, bind, and save custom keyboard shortcuts (e.g., `Ctrl + C`, `Alt + F4`).
* **Hardware Design:** Powered by the ATmega32U4 microcontroller, featuring 6 Gateron mechanical switches and an incremental rotary encoder for additional control (e.g., media/volume).
* **Modular Ergonomics:** Custom 3D-printed enclosure with embedded neodymium magnets for quick and easy typing angle adjustments.

## Repository Structure
* `/Hardware` - Altium Designer project, schematics, PCB layouts, and Gerber files (Will be uploaded).
* `/Firmware` - C source code for the ATmega32U4 microcontroller.
* `/App` - Python source code for the Hive Center desktop application.
* `/Mechanical` - STL files and 3D models for the enclosure (Will be uploaded).

