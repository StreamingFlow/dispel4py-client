from laminar.conversion.ConvertPy import ConvertPyToAST

# calling from command line
if __name__ == '__main__':
    # print("hello world")
    codeStr = '''
class isEven(IterativePE):
    def __init__(self):
        IterativePE.__init__(self)
    def _process(self, input):
        if (input % 2 == 0):
            return True

        else:
            return False'''
    converted = ConvertPyToAST(codeStr, False)
    print(converted.result)

