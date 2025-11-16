# Instructions for Creating and Configuring the Bluetooth Gate

---

## 📦 Preparation

1. Purchase the **ESP32-S3-DEV-KIT-N8R8** board:  
   https://www.waveshare.com/wiki/ESP32-S3-DEV-KIT-N8R8

2. Download the firmware here:  
   [*FIRMWARE*](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/Ritar_BT_Gate_Firmware_1_1.FACTORY.bin)

3. Open the online flashing tool (supported browsers: Edge, Chrome, Opera):  
   https://esptool.spacehuhn.com/

4. Press and hold the **BOOT** button on the board:

   ![images/00.png](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/00_board_ESP32-S3-DEV-KIT-N8R8.png)

5. **While holding BOOT, connect the board to your computer via USB.  
   Wait ~10 seconds and release the button.**

6. Click **Connect**:

   ![Image 01](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/01_webflasher.jpg)

7. Select the COM port as shown:

   ![Image 02](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/02_webflasher.jpg)

8. Delete all default flashing entries:

   ![Image 03](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/03_webflasher.jpg)

9. Create a new flashing rule:

   ![Image 04](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/04_webflasher.jpg)

10. You will see a new rule:

    ![Image 05](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/05_webflasher.jpg)

    Click **Select** and choose the firmware file you downloaded.

11. The final setup should look like this:

    ![Image 07](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/07_webflasher.jpg)

    Press **Program**.

12. When you see this warning, choose **Continue**:

    ![Image 08](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/08_webflasher.jpg)

13. After successful flashing:

    ![Image 09](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/09_webflasher.jpg)

14. **Disconnect and reconnect the USB cable several times to ensure the board exits BOOT mode.**

---

## 📱 Initial Setup

1. After successful flashing, the device will boot normally and create an open Wi-Fi network **Ritar BT Gate**:

   ![Image 10](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/10_phone.jpg)

2. Connect to the Wi-Fi network (examples):

   ![Image 11](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/11_phone.jpg)

   ![Image 12](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/12_phone.jpg)

   ![Image 13](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/13_phone.jpg)

3. Open a browser and enter the gate's web interface URL:

   ![Image 14](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/14_phone.jpg)

4. You will see the login screen:

   ![Image 15](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/15_phone.jpg)

5. Enter default credentials:  
   - username: **admin**  
   - password: **1234**

   ![Image 16](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/16_phone.jpg)

6. Go to Wi-Fi connection settings:

   ![Image 17](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/17_phone.jpg)

7. Select your Wi-Fi network or configure manually:

   ![Image 18](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/18_phone.jpg)

   ![Image 19](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/19_phone.jpg)

   ![Image 20](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/20_phone.jpg)

8. After successful connection, the gate will reboot and obtain an IP via DHCP.

9. **Find the IP address assigned by your router.  
   Optionally assign it permanently (by MAC reservation) or configure static IP later in the gate.**

10. **Place the gate close to your master battery.**

---

## 🛠️ Gate Configuration and Testing

1. Open the gate's IP address in your browser and log in:

   ![Image 21](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/21_computer.jpg)

2. The start menu will appear:

   ![Image 22](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/22_computer.jpg)

3. Open admin settings and change the default password.  
   Set the time zone if needed:

   ![Image 24](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/24_computer.jpg)

4. Configure static IP (optional):

   ![Image 25](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/25_computer.jpg)

5. Open master battery settings and enter your battery's MAC address:

   ![Image 26](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/26_computer.jpg)

   ![Image 27](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/27_computer.jpg)

6. If the MAC is unknown, scan for nearby devices multiple times:

   ![Image 28](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/28_computer.jpg)

7. Look for devices with `svcdata = AC_...` (Ritar-compatible RDAC batteries).  
   Copy the MAC address, paste it, press **Save Target** and **Connect**:

   ![Image 29](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/29_computer.jpg)

8. Upon successful connection, you will see console messages similar to this:

   ![Image 30](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/30_computer.jpg)

9. You can verify the connection using the original [**Bluetooth Li**](https://play.google.com/store/apps/details?id=com.ritarpower.bluetooth.li&hl=ru) app:

   ![Image 31](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/31_native_app.jpg)

   ![Image 32](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/32_native_app.jpg)

10. When BluetoothLi connects, you will see continuous log output:

    ![Image 33](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/33_computer.jpg)

---

## 🏠 Connecting to the Home Assistant Ritar-BMS Add-on

1. To use the gate with the **Ritar-BMS** Home Assistant add-on, switch operation mode using the **Toggle Mode** button:

   ![Image 34](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/screenshots/34_computer.jpg)

> Note: The gate works in **one** mode at a time — either with the original app or with the Ritar-BMS add-on.  
> API-based integration will be added in upcoming releases.

---
