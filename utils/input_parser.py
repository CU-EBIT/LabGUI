# A bunch of functions for fortran IO
def parseVar(input):
    string = str(input)
    if string.endswith('d0') or string.endswith('D0'):
        var = string.replace('D0','').replace('d0','')
        return float(var)
    if string == 't' or string == 'T':
        return True
    if string == 'f' or string == 'F':
        return False
    if isInt(string):
        return int(string)
    if isFloat(string):
        return float(string)
    return string

def parseLine(input):
    vars = input.split()
    ret = []
    for var in vars:
        ret.append(parseVar(var))
    return ret

def toStr(input):
    if isinstance(input, bool):
        return 't' if input else 'f'
    return str(input)

def serializeArr(input):
    output = ''
    n = 0
    for var in input:
        if n == 0:
            output = toStr(var)
        else:
            output = output + ' ' + toStr(var)
        n = n + 1
    return output

def serialize(*input):
    return serializeArr(input)

def isInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def isFloat(s):
    try: 
        float(s)
        return True
    except ValueError:
        return False