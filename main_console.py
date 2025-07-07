# main_console.py

def print_table(headers, rows, total_width=None, fixed_col_widths=None):
    num_cols = len(headers)

    # Compute max width per column based on content and header (ignore None rows)
    content_rows = [row for row in rows if row is not None]

    if fixed_col_widths:
        # Use provided fixed widths
        col_widths = fixed_col_widths
    else:
        col_widths = [
            max(len(str(headers[i])), max(len(str(row[i])) for row in content_rows))
            for i in range(num_cols)
        ]

        # Calculate minimum total width with borders and spacing
        min_total_width = sum(col_widths) + (num_cols - 1) * 3 + 2 * (num_cols + 1)
        width = max(total_width or 0, min_total_width)

        # Distribute extra space equally to columns
        extra_space = width - min_total_width
        if extra_space > 0:
            add_each = extra_space // num_cols
            remainder = extra_space % num_cols
            for i in range(num_cols):
                col_widths[i] += add_each
                if i < remainder:
                    col_widths[i] += 1

    def print_line(char='═'):
        print('╔' + '╦'.join([char * (w + 2) for w in col_widths]) + '╗')

    def print_header():
        print('╠' + '╬'.join(['═' * (w + 2) for w in col_widths]) + '╣')

    def print_footer():
        print('╚' + '╩'.join(['═' * (w + 2) for w in col_widths]) + '╝')

    def print_separator():
        print('╟' + '┼'.join(['─' * (w + 2) for w in col_widths]) + '╢')

    print_line()
    header_cells = [f' {headers[i].ljust(col_widths[i])} ' for i in range(num_cols)]
    print('║' + '║'.join(header_cells) + '║')
    print_header()

    for row in rows:
        if row is None:
            print_separator()
        else:
            row_cells = []
            for i in range(num_cols):
                cell_text = str(row[i])
                # Right-align last column if fixed_col_widths is set (usually Code column)
                if fixed_col_widths and i == num_cols - 1:
                    cell_text = cell_text.rjust(col_widths[i])
                else:
                    cell_text = cell_text.ljust(col_widths[i])
                row_cells.append(f' {cell_text} ')
            print('║' + '║'.join(row_cells) + '║')

    print_footer()


def print_config_table(config, total_width=110):
    connection_type = config.get('connection_type', 'ethernet').lower()

    if connection_type == 'ethernet':
        groups = [
            ['connection_type', 'rs485gate_ip', 'rs485gate_port'],
            ['mqtt_broker', 'mqtt_port', 'mqtt_username', 'mqtt_password'],
            ['battery_model', 'num_batteries', 'console_output_enabled', 'zero_pad_cells', 'queries_delay', 'next_battery_delay', 'read_timeout', 'warnings_enabled'],
        ]
    elif connection_type == 'serial':
        groups = [
            ['connection_type', 'serial_port', 'serial_baudrate'],
            ['mqtt_broker', 'mqtt_port', 'mqtt_username', 'mqtt_password'],
            ['battery_model', 'num_batteries', 'console_output_enabled', 'zero_pad_cells', 'queries_delay', 'next_battery_delay', 'read_timeout', 'warnings_enabled'],
        ]
    else:
        groups = [
            ['connection_type'],
            ['mqtt_broker', 'mqtt_port', 'mqtt_username', 'mqtt_password'],
            ['battery_model', 'num_batteries', 'console_output_enabled', 'zero_pad_cells', 'queries_delay', 'next_battery_delay', 'read_timeout', 'warnings_enabled'],
        ]

    logical_rows = []
    for i, group in enumerate(groups):
        if i > 0:
            logical_rows.append(None)  # separator placeholder
        for key in group:
            value = config.get(key)
            if value is None or value == '':
                value = '—'
            elif isinstance(value, bool):
                value = str(value)
            elif key == 'mqtt_password':
                value = '******'
            logical_rows.append([key.replace('_', ' ').title(), value])

    headers = ["Configuration Parameter", "Value"]
    print_table(headers, logical_rows, total_width)


def print_inverter_protocols_table(protocols, total_width=108):
    if isinstance(protocols, dict):
        items = sorted(protocols.items())
    else:
        items = protocols

    col3_width = 5  # Fixed width for Code column
    col1_width = total_width - col3_width - 7  # Rest for Protocol column (7 = borders + spacing)

    def truncate_text(text, max_len):
        if len(text) > max_len and max_len > 3:
            return text[:max_len - 3] + "..."
        return text

    rows = []
    for code, desc in items:
        protocol_name = truncate_text(desc, col1_width)
        rows.append([protocol_name, str(code)])

    print_table(
        ["Inverter Protocols Supported by Ritar BMS", "Code"],
        rows,
        total_width,
        fixed_col_widths=[col1_width, col3_width]
    )


def print_inverter_protocols_table_batteries(protocols_list, total_width=106):
    col1_width = 18  # Battery column
    col3_width = 5   # Code column
    col2_width = total_width - col1_width - col3_width - 8  # Borders & spacing

    def truncate_text(text, max_len):
        if len(text) > max_len and max_len > 3:
            return text[:max_len - 3] + "..."
        return text

    rows = []
    for bat_id, code, desc in protocols_list:
        battery_name = f"Battery {bat_id}" if isinstance(bat_id, int) else str(bat_id)
        protocol_code = str(code) if code is not None else ""
        protocol_name = truncate_text(desc, col2_width)
        rows.append([battery_name, protocol_name, protocol_code])

    # Determine common protocol
    codes = [code for _, code, _ in protocols_list if code is not None]
    descs = [desc for _, _, desc in protocols_list]

    if codes and all(c == codes[0] for c in codes):
        common_protocol_name = descs[0]
        common_protocol_code = codes[0]
        common_protocol_trunc = truncate_text(common_protocol_name, col2_width)
        common_protocol_display = [
            "Common Protocol",
            common_protocol_trunc,
            str(common_protocol_code)
        ]
    else:
        common_protocol_display = [
            "Common Protocol",
            "Mixed or Unknown",
            ""
        ]

    rows.append(None)  # Separator row
    rows.append(common_protocol_display)

    print_table(
        ["Battery", "Inverter Protocol", "Code"],
        rows,
        total_width,
        fixed_col_widths=[col1_width, col2_width, col3_width]
    )

def print_presets_table(presets_dict, total_width=106):
    col1_width = 10  # Battery column
    col3_width = 7   # Value column (numbers)
    col2_width = total_width - col1_width - col3_width - 8  # Borders and spacing

    def truncate_text(text, max_len):
        if len(text) > max_len and max_len > 3:
            return text[:max_len - 3] + "..."
        return text

    rows = []
    battery_ids = list(presets_dict.keys())
    for i, bat_id in enumerate(battery_ids):
        values = presets_dict[bat_id]
        first_row = True
        for label, value in values.items():
            truncated_label = truncate_text(label, col2_width)
            val_str = str(value) if value is not None else "—"
            if first_row:
                rows.append([f"Battery {bat_id}", truncated_label, val_str])
                first_row = False
            else:
                rows.append(["", truncated_label, val_str])
        if i != len(battery_ids) - 1:
            rows.append(None)  # separator row

    print_table(
        ["Battery", "EEPROM presets from all batteries...", "Value"],
        rows,
        total_width,
        fixed_col_widths=[col1_width, col2_width, col3_width]
    )
