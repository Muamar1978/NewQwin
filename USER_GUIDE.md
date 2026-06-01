# 🌪️ Air Quality Dispersion Model (GPAI) - Beginner Guide

Welcome! This guide will help you get the application running on your Windows computer in just a few clicks.

---

## 🛠️ Prerequisites

1.  **Python 3.11 or newer**:
    *   If you don't have it, download and install it from [python.org/downloads](https://www.python.org/downloads/).
    *   > [!IMPORTANT]
        > During installation, you **MUST** check the box that says **"Add Python to PATH"**.

---

## 🚀 How to Install (First Time Only)

1.  Open your project folder.
2.  Find the file **`setup.bat`** (or just `setup` with a gear icon).
3.  **Double-click it**.
4.  A black Command Prompt window will open. Wait for it to finish installing (this takes **5 to 10 minutes**).
5.  When you see `SETUP COMPLETED SUCCESSFULLY!`, press any key to close the window.

---

## 💻 How to Run the App

1.  **Double-click `run.bat`** (or just `run`).
2.  Wait a few seconds. The app will automatically open your web browser to:
    *   `http://localhost:5000`
3.  > [!CAUTION]
    > **Keep the black window open** while using the app. If you close it, the app will stop.

---

## 🛑 How to Stop the App

1.  Go to the black Command Prompt window.
2.  Press **`Ctrl + C`** on your keyboard, OR simply **close the window**.

---

## 🔍 Troubleshooting

If the app doesn't start or you see errors:

*   **Standard Fix**: Run **`diagnostic.bat`**. It will check your system and create a report named `diagnostic_report.txt`.
*   **"Python not found"**: Reinstall Python and make sure to check "Add Python to PATH".
*   **"Setup fails"**: Ensure you have an active internet connection.
*   **Browser window doesn't open**: Manually open your browser and type: `http://localhost:5000`

---

## 📂 Data Files

The app needs these files in the folder to work correctly:
*   `road1.shp` to `road4.shp` (Map data)
*   `ERA5_P0INTS.csv` (Weather data)
*   `Hotspots_AllPollutants_GIS.csv` (Pollution data)

---

*Need more help? Check the `ARCHITECTURE_UPDATE.md` for technical details.*
