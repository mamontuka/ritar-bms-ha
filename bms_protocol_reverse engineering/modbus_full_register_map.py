# Full register map matching vendor addresses

REG_CURRENT = 0                   # m_Current = 0
REG_VOLTAGE_OF_PACK = 1           # m_Voltage_of_pack = 1
REG_SOC = 2                       # m_SOC = 2
REG_SOH = 3                      # m_SOH = 3
REG_REMAIN_CAPACITY = 4           # m_Remain_capacity = 4
REG_FULL_CAPACITY = 5             # m_Full_capacity = 5
REG_DESIGN_CAPACITY = 6           # m_Design_capacity = 6
REG_BATTERY_CYCLE_COUNTS = 7      # m_Battery_cycle_counts = 7
REG_SOLAR_CURRENT = 8             # m_Solar_Current = 8
REG_WARNING_FLAG_HIGH = 9         # m_Warning_flagh = 9
REG_WARNING_FLAG_LOW = 10         # m_Warning_flagl = 10
REG_PROTECTION_FLAG_HIGH = 11     # m_Protection_flagh = 11
REG_PROTECTION_FLAG_LOW = 12      # m_Protection_flagl = 12
REG_STATUS_FAULT_FLAG_HIGH = 13   # m_Status_Fault_flagh = 13
REG_STATUS_FAULT_FLAG_LOW = 14    # m_Status_Fault_flagl = 14
REG_BALANCE_STATUS = 15           # m_Balance_status = 15

# Skipping to MAC which is at 20
REG_MAC = 20                     # m_Mac = 20

REG_CHARGER_VOLTAGE = 31          # m_Charger_Voltage = 31
REG_INVERTER_SELECT = 32          # m_Inverter_Select = 32
REG_TOTAL_CURRENT = 33            # m_Total_Current = 33

REG_CELL_VOLTAGE = 40             # m_Cell_voltage = 40

REG_CELL_TEMPERATURE = 120        # m_Cell_temperature = 120

REG_MOSFET_TEMPERATURE = 145      # m_MOSFET_temperature = 145
REG_ENVIRONMENT_TEMPERATURE = 146 # m_Env_temperature = 146  <-- Added missing register 146

REG_CELL_MAX_VOLTAGE = 147        # m_Cell_Max_Volt = 147
REG_CELL_MAX_VOLTAGE_NUMBER = 148 # m_Cell_Max_Volt_Num = 148
REG_CELL_MIN_VOLTAGE = 149        # m_Cell_Min_Volt = 149
REG_CELL_MIN_VOLTAGE_NUMBER = 150 # m_Cell_Min_Volt_Num = 150

REG_CELL_MAX_TEMPERATURE = 151    # m_Cell_Max_Tem = 151
REG_CELL_MAX_TEMPERATURE_NUMBER = 152  # m_Cell_Max_Tem_Num = 152
REG_CELL_MIN_TEMPERATURE = 153    # m_Cell_Min_Tem = 153
REG_CELL_MIN_TEMPERATURE_NUMBER = 154  # m_Cell_Min_Tem_Num = 154

REG_POSITIVE_TEMPERATURE = 155    # m_Pos_Tem = 155
REG_NEGATIVE_TEMPERATURE = 156    # m_Neg_Tem = 156

REG_PACK_OV_ALARM = 160           # m_Pack_OV_alarm = 160
REG_PACK_OV_PROTECTION = 161      # m_Pack_OV_protection = 161
REG_PACK_OV_RELEASE_PROTECTION = 162  # m_Pack_OV_release_protection = 162
REG_PACK_OV_PROTECTION_DELAY_TIME = 163 # m_Pack_OV_protection_delay_time = 163

REG_CELL_OV_ALARM = 164           # m_Cell_OV_alarm = 164
REG_CELL_OV_PROTECTION = 165      # m_Cell_OV_protection = 165
REG_CELL_OV_RELEASE_PROTECTION = 166   # m_Cell_OV_release_protection = 166
REG_CELL_OV_PROTECTION_DELAY_TIME = 167  # m_Cell_OV_protection_delay_time = 167

REG_PACK_UV_ALARM = 168           # m_Pack_UV_alarm = 168
REG_PACK_UV_PROTECTION = 169      # m_Pack_UV_protection = 169
REG_PACK_UV_RELEASE_PROTECTION = 170   # m_Pack_UV_release_protection = 170
REG_PACK_UV_PROTECTION_DELAY_TIME = 171  # m_Pack_UV_protection_delay_time = 171

REG_CELL_UV_ALARM = 172           # m_Cell_UV_alarm = 172
REG_CELL_UV_PROTECTION = 173      # m_Cell_UV_protection = 173
REG_CELL_UV_RELEASE_PROTECTION = 174   # m_Cell_UV_release_protection = 174
REG_CELL_UV_PROTECTION_DELAY_TIME = 175  # m_Cell_UV_protection_delay_time = 175

REG_CHARGING_OC_ALARM = 176       # m_Charging_OC_alarm = 176
REG_CHARGING_OC_PROTECTION = 177  # m_Charging_OC_protection = 177
REG_CHARGING_OC_PROTECTION_DELAY_TIME = 178 # m_Charging_OC_protection_delay_time = 178

REG_DISCHARGING_OC_ALARM = 179    # m_Discharging_OC_alarm = 179
REG_DISCHARGING_OC_PROTECTION = 180  # m_Discharging_OC_protection = 180
REG_DISCHARGING_OC_PROTECTION_DELAY_TIME = 181 # m_Discharging_OC_protection_delay_time = 181

REG_DISCHARGING_OC2_PROTECTION = 182 # m_Discharging_OC2_protection = 182
REG_DISCHARGING_OC2_PROTECTION_DELAY_TIME = 183  # m_Discharging_OC2_protection_delay_time = 183

REG_CHARGING_OT_ALARM = 184       # m_Charging_OT_alarm = 184
REG_CHARGING_OT_PROTECTION = 185  # m_Charging_OT_protection = 185
REG_CHARGING_OT_RELEASE_PROTECTION = 186  # m_Charging_OT_release_protection = 186

REG_DISCHARGING_OT_ALARM = 187    # m_Discharging_OT_alarm = 187
REG_DISCHARGING_OT_PROTECTION = 188  # m_Discharging_OT_protection = 188
REG_DISCHARGING_OT_RELEASE_PROTECTION = 189  # m_Discharging_OT_release_protection = 189

REG_CHARGING_UT_ALARM = 190       # m_Charging_UT_alarm = 190
REG_CHARGING_UT_PROTECTION = 191  # m_Charging_UT_protection = 191
REG_CHARGING_UT_RELEASE_PROTECTION = 192  # m_Charging_UT_release_protection = 192

REG_DISCHARGING_UT_ALARM = 193    # m_Discharging_UT_alarm = 193
REG_DISCHARGING_UT_PROTECTION = 194  # m_Discharging_UT_protection = 194
REG_DISCHARGING_UT_RELEASE_PROTECTION = 195  # m_Discharging_UT_release_protection = 195

REG_MOSFET_OT_ALARM = 196         # m_MOSFET_OT_alarm = 196
REG_MOSFET_OT_PROTECTION = 197    # m_MOSFET_OT_protection = 197
REG_MOSFET_OT_RELEASE_PROTECTION = 198  # m_MOSFET_OT_release_protection = 198

REG_ENVIRONMENT_OT_ALARM = 199    # m_Environment_OT_alarm = 199
REG_ENVIRONMENT_OT_PROTECTION = 200  # m_Environment_OT_protection = 200
REG_ENVIRONMENT_OT_RELEASE_PROTECTION = 201  # m_Environment_OT_release_protection = 201

REG_ENVIRONMENT_UT_ALARM = 202    # m_Environment_UT_alarm = 202
REG_ENVIRONMENT_UT_PROTECTION = 203  # m_Environment_UT_protection = 203
REG_ENVIRONMENT_UT_RELEASE_PROTECTION = 204  # m_Environment_UT_release_protection = 204

REG_BALANCE_START_CELL_VOLTAGE = 205  # m_Balance_start_cell_voltage = 205
REG_BALANCE_START_DELTA_VOLTAGE = 206  # m_Balance_start_delta_voltage = 206

REG_PACK_FULL_CHARGE_VOLTAGE = 207  # m_Pack_full_charge_voltage = 207
REG_PACK_FULL_CHARGE_CURRENT = 208  # m_Pack_full_charge_current = 208

REG_CELL_SLEEP_VOLTAGE = 209       # m_Cell_sleep_voltage = 209
REG_CELL_SLEEP_DELAY_TIME = 210    # m_Cell_sleep_delay_time = 210
REG_SHORT_CIRCUIT_PROTECT_DELAY_TIME = 211  # m_Short_circuit_protect_delay_time = 211
REG_SOC_ALARM_THRESHOLD = 212      # m_SOC_alarm_threshold = 212

REG_CHARGING_OC2_PROTECTION = 213  # m_Charging_OC2_protection = 213
REG_CHARGING_OC2_PROTECTION_DELAY_TIME = 214  # m_Charging_OC2_protection_delay_time = 214

REG_SOC1 = 215                   # m_SOC1 = 215
REG_SOC2 = 216                   # m_SOC2 = 216
REG_SOH1 = 217                   # m_SOH1 = 217
REG_SOH2 = 218                   # m_SOH2 = 218
REG_REMAIN_CAPACITY1 = 219       # m_Remain_CAP1 = 219
REG_REMAIN_CAPACITY2 = 220       # m_Remain_CAP2 = 220
REG_FULL_CAPACITY1 = 221         # m_Full_CAP1 = 221
REG_FULL_CAPACITY2 = 222         # m_Full_CAP2 = 222

REG_AFE_CURRENT_ZERO = 223       # m_Afe_current_zero = 223
REG_AFE_POS_CURRENT_CALIB = 224  # m_Afe_pos_current_calib = 224
REG_AFE_NEG_CURRENT_CALIB = 225  # m_Afe_nec_current_calib = 225  (note: "nec" is typo of "neg" in vendor)
REG_MCU_CURRENT_ZERO = 226       # m_Mcu_current_zero = 226
REG_MCU_POS_CURRENT_CALIB = 227  # m_Mcu_pos_current_calib = 227
REG_MCU_NEG_CURRENT_CALIB = 228  # m_Mcu_nec_current_calib = 228

REG_PACK_VOLTAGE_ZERO = 229      # m_Pack_volt_zero = 229
REG_PACK_VOLTAGE_CALIB = 230     # m_Pack_volt_calib = 230

REG_CHARGE_MOS_CONTROL = 231     # m_Charge_MOS_Control = 231
REG_DISCHARGE_MOS_CONTROL = 232  # m_Discharge_MOS_Control = 232
REG_PRE_MOS_CONTROL = 233        # m_Pre_MOS_Control = 233
REG_FAN_MOS_CONTROL = 234        # m_FAN_MOS_Control = 234
REG_LIMIT_MOS_CONTROL = 235      # m_Limit_MOS_Control = 235

REG_DRY_CONTACT1_CONTROL = 236   # m_DryContact1_Control = 236
REG_DRY_CONTACT2_CONTROL = 237   # m_DryContact2_Control = 237
REG_PC_MOS_CONTROL = 238         # m_PC_MOS_Control = 238

REG_YEAR = 239                  # m_Year = 239
REG_MONTH = 240                 # m_Month = 240
REG_DAY = 241                   # m_Day = 241
REG_HOUR = 242                  # m_Hour = 242
REG_MINUTE = 243                # m_Munite = 243  (vendor typo: "Munite" instead of "Minute")
REG_SECOND = 244                # m_Second = 244

REG_RESTORE_DEFAULT_PARAMETERS = 245  # m_Restore_Default_Paramters = 245 (typo in vendor)
REG_RECORD_LENGTH = 246              # m_RecordLength = 246
REG_RECORD_HISTORY = 247             # m_RecordHistory = 247

REG_SLEEP = 280                    # m_Sleep = 280

REG_PN_OT_ALARM = 283             # m_PN_OT_Alarm = 283
REG_PN_OT_PROTECT = 284           # m_PN_OT_Protect = 284
REG_PN_OT_RELEASE = 285           # m_PN_OT_Release = 285
REG_PN_OT_DELAY = 286             # m_PN_OT_Delay = 286

REG_FS_MOS_CONTROL = 287          # m_FS_MOS_Control = 287

REG_VERSION_INFORMATION = 290    # m_Version_information = 290
REG_MODEL_SN = 300                # m_Model_SN = 300
REG_PACK_SN = 310                # m_PACK_SN = 310

REG_END = 320                    # m_end = 320
