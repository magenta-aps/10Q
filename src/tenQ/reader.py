import sys
from typing import List, Dict
from openpyxl import Workbook

from .writer import (
    TenQFixWidthFieldLineTransactionType10,
    TenQFixWidthFieldLineTransactionType24,
    TenQFixWidthFieldLineTransactionType26,
)

trans_type_map = {
    '10': TenQFixWidthFieldLineTransactionType10,
    '24': TenQFixWidthFieldLineTransactionType24,
    '26': TenQFixWidthFieldLineTransactionType26,
}


def read_10q_file(filename: str) -> List[Dict]:

    with open(filename, "r") as fp:
        line_no = 1
        line_data = {}
        all_line_data = []
        for line in fp.readlines():
            trans_type = line[4:6]
            if trans_type in trans_type_map:
                # Each time we encounter a type 10, start a new dict. Other lines update the previous dict
                if trans_type == '10':
                    if line_data:
                        all_line_data.append(line_data)
                    line_data = {}

                # Get fieldspec based on trans_type
                fieldspec = trans_type_map[trans_type].fieldspec

                # Loop over field spec (it's an ordered tuple).
                # Each field specifies its length, so the accumulated sum of lengths is the position we read from
                pos = 0
                for fieldname, fieldlength, default in fieldspec:
                    if fieldname != 'trans_type':  # Don't save trans_type
                        line_data[fieldname] = line[pos:pos+fieldlength]
                    pos += fieldlength

                # Save line numbers
                if '10q_line_no' not in line_data:
                    line_data['10q_line_no'] = []
                line_data['10q_line_no'].append(line_no)
            else:
                print(f"Unrecognized trans_type {trans_type} on line {line_no}")
            line_no += 1

        # Last instance of line_data
        if line_data:
            all_line_data.append(line_data)

    return all_line_data


def save_to_excel(data: List[Dict], filename: str):

    # Convert dicts' keys into a list of headers, with 10q_line_no first
    headers_dict = {'10q_line_no': True}
    for item in data:
        headers_dict.update({key: True for key in item.keys()})
    headers = list(headers_dict.keys())

    # Create spreadsheet
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(headers)
    for item in data:
        row = []
        for header in headers:
            value = item.get(header, '')
            if type(value) == list:
                value = ','.join(map(str, value))
            row.append(value)
        ws.append(row)
    wb.save(filename)


if __name__ == '__main__':
    data = read_10q_file(sys.argv[1])
    save_to_excel(data, sys.argv[2])
