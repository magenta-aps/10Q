import sys


print(f"Name: {__name__}")
print(f"Package: {__package__}")

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

def read_10q_file(filename):
    with open(filename, "r") as fp:
        line_no = 1
        line_data = {}
        all_line_data = []
        for line in fp.readlines():
            trans_type = line[4:6]
            if trans_type in trans_type_map:
                if trans_type == '10':
                    if line_data:
                        all_line_data.append(line_data)
                    line_data = {}
                fieldspec = trans_type_map[trans_type].fieldspec
                pos = 0
                for fieldname, fieldlength, default in fieldspec:
                    if fieldname != 'trans_type':
                        line_data[fieldname] = line[pos:pos+fieldlength]
                    pos += fieldlength
                if '10q_line_no' not in line_data:
                    line_data['10q_line_no'] = []
                line_data['10q_line_no'].append(line_no)
            else:
                print(f"Unrecognized trans_type {trans_type} on line {line_no}")
            line_no += 1
        if line_data:  # Last one
            all_line_data.append(line_data)
    return all_line_data


if __name__ == '__main__':
    read_10q_file(sys.argv[1])
