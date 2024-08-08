# antlr4 -v 4.13.0 -Dlanguage=Python3 PythonParser.g4
from antlr4 import * #antlr4-python3-runtime==4.13.1
from antlr4.tree.Trees import Trees
from Aroma.PythonLexer import PythonLexer
from Aroma.PythonParser import PythonParser
from antlr4.tree.Tree import TerminalNode, TerminalNodeImpl, Tree, ParseTree

from enum import Enum

import json

# takes a function as input and creates an equivalent PE
    # ProducerPE (takes no input, returns an output)
    # IterativePE (takes an input, returns an output)
    # ConsumerPE (takes an input, returns no output)

# create an __init__ that just creates it's type

# create an _process that is just the function

# drop any functions that take more than 1 arguement


# the PE types currently supported

# note that the tests we are given may require additional context to be functional
# (ie global variables) but as a testing dataset we do not need to worry about this
 
class PETYPE(Enum):
    PRODUCER = "ProducerPE"
    CONSUMER = "ConsumerPE"
    ITERATIVE = "IterativePE"


class ConvertToPE:
    ruleNames = []
    pe = None
    className = None
    # perform parsing and lexing to ensure ease of traversal to the appropriate terms
    def __init__(self, input, isFile, appendID = None):
   
        if isFile:
            input_stream = FileStream(input)
        else:
            input_stream = InputStream(input)


        lexer = PythonLexer(input_stream)
        vocab = lexer.symbolicNames

        stream = CommonTokenStream(lexer)
        parser = PythonParser(stream)
        # print(stream)
        tree = parser.file_input()
        # print(Trees.toStringTree(tree, None, parser))
        # print(input)

        self.setRuleNames(parser)

        # get the number of parameters
        numParams, funcName, funcTree, paramText = self.getDefDetails(tree, parser)

        # reject if > 1 param
        
        if numParams > 1:
            return

        # if the function is from a class then we remove this as it will
        # be added later
        if numParams == 1 and paramText.strip() == "self":
            numParams = 0
            paramText = "" 
        numReturnVals = self.detectReturn(tree, parser)

        # if there is no return statement as well as no return params
        # then this will be considered none
        if numReturnVals == None:
            numReturnVals = 0

        if numReturnVals > 1:
            return
        # print(numReturnVals)
        # print(numParams)
        
        peType = self.getPEType(numParams, numReturnVals)

        # print(peType)
        if peType != None:
            self.pe = self.constructPE(peType, funcName, funcTree, paramText, stream, appendID)

    def setRuleNames(self, parser):
        self.ruleNames = parser.ruleNames

    def getRuleName(self, tree):
        return self.ruleNames[tree.getRuleIndex()]

    # gets the text leading / trailing the token
    # (ie the indentation and line breaks etc)
    def getLeadingOrTrailing(self, tree, tokens, isBefore):
        lastIndexOfToken = tree.getSymbol().tokenIndex
        ws = None
        text = ""
        HIDDEN = 1
        if(lastIndexOfToken < 0):
            print("last index of token < 0")
            return ""
        if(isBefore):
            ws = tokens.getHiddenTokensToLeft(lastIndexOfToken, HIDDEN)
        elif(lastIndexOfToken >= 0 or lastIndexOfToken == -2):
            ws = tokens.getHiddenTokensToRight(lastIndexOfToken, HIDDEN)
        if(ws != None):
            for wst in ws:

                text += wst.text
        return text
    



    def getPEType(self, numParams, numReturnVals):
        # invalid in current setup
        if numParams == 0 and numReturnVals == 0:
            return None
        # takes 1 param and has no return
        if numParams == 1 and numReturnVals == 0:
            return PETYPE.CONSUMER
            
        # takes no params and returns a var
        elif numParams == 0 and numReturnVals == 1:
            return PETYPE.PRODUCER
        # takes a param and returns a var
        else:
            return PETYPE.ITERATIVE

    # find the function definition and count the number of parameters
    # not really concerned about efficiency atm

    def getDefDetails(self, tree, parser):
        
        numChildren = tree.getChildCount()
        hasLeaf = False

        # if at the end of a leaf go no further
        if(numChildren == 0):
            return None
        
        thisRuleName = self.getRuleName(tree)

        # this is the closest ruleNode (and is not nested as function def), could search for the terminalNode "params"
        # but this would be less efficient as this way we are able to prune and not check terminalNodes
        if(thisRuleName == "function_def_raw"):
            # from a function def, we know that the params branch is the 4th child
            # parameters is then the 1st child
            # we can use the number here to determine information about the type of pe to create

            # print(Trees.toStringTree(tree.getChild(3).getChild(0), None, parser))
            # print(tree.getChild(3).getText())

            funcName = tree.getChild(1)
            paramTag = tree.getChild(3)
            # text of the params

            

            # check if there are any parameters and if so how many
            if paramTag.getChild(0) == None:
                numParameters = 0
                paramText = ""
                funcTree = tree.getChild(5) # (skips all def)
            else:
                numParameters = paramTag.getChild(0).getChildCount()
                paramText = paramTag.getText()
                funcTree = tree.getChild(6) # (skips all def and params)
            return numParameters, funcName, funcTree, paramText


        for i in range(numChildren):
            childTree = tree.getChild(i)
            # nothing further as terminal node (ie not a ruleNode)
            if(isinstance(childTree, TerminalNodeImpl)):
                return None
            
            # check deeper in the stack
            else:
                child = self.getDefDetails(childTree, parser)
                if child != None:
                    return child




    # iterate through a function until we find a return statement or dedent out of the function
    def detectReturn(self, tree, parser):
        numChildren = tree.getChildCount()
        hasLeaf = False

        # if at the end of a leaf go no further
        if(numChildren == 0):
            return None
        
        thisRuleName = self.getRuleName(tree)
        # print(thisRuleName)
        
        # cannot perform the same optimisation as above due to the return stmt
        # being overly nested
        if(thisRuleName == "return_stmt"):
            # no params
            if tree.getChildCount() == 1:
                return 0
            
            # NOTE if the number of parameters is > 1, then the commas are also classed as children
            # use n+1 / 2 for number of parameters returned
           
            return int((tree.getChild(1).getChildCount() + 1) / 2)
        
        for i in range(numChildren):
            childTree = tree.getChild(i)
            child = self.detectReturn(childTree, parser)
            if child != None:
                return child


    # create a class, and init for the appropriate type
    # name class using function name
    # put inputted function code into the _process function
    def constructPE(self, peType: PETYPE, funcName, funcTree, paramText, tokens, appendID):
        # adds the self param as appropriate
        if paramText.strip() == "":
            paramText = "self"
        else:
            paramText = "self, " + paramText.strip()

        # adds a unique identifier if required
        if appendID != None:
            funcName = str(funcName) + "_" + str(appendID)
        self.className = str(funcName)
        # capitalise the first letter so that it is the appropriate form for a class
        pe = "class " + str(funcName).capitalize() + "(" + peType.value + "):\n"
        pe += "    def __init__(self):\n        " + peType.value + ".__init__(self)\n"
        pe += "    def _process("+ paramText + "):\n"

        # split by line so that we can add tabs to each as necessary
        # remove leading new lines (but not whitespace) from text before splitting
        processLines = self.createWithHidden(funcTree, "", tokens).strip("\n"). split("\n")
        # print(processLines)
        # reconcatenate the list (add tabs to each element in the list then join with \n)
        # using 4 spaces instead of \t (reqiured as we are going from function to class level indentation)
        processLines = '\n'.join([''.join(("    ", line)) for line in processLines])
        pe += processLines
        return pe

        # iterate through tree and recover the 
        # print(funcTree.getText())


    # reconstruct the inside of the function
    # could just string split the input, but this is more reliable for comments etc
    def createWithHidden(self, tree, text, tokens):
        numChildren = tree.getChildCount()
        hasLeaf = False


         # if at the end of a leaf go no further
        if(numChildren == 0):
            return None
        
        thisRuleName = self.getRuleName(tree)
        
        # if(isinstance(tree, RuleNode)):
        #     print(tree.getText())


        for i in range(numChildren):
            childTree = tree.getChild(i)
            if(isinstance(childTree, TerminalNodeImpl)):
                # remove the explicit newline, indent and dedent chars
                text += self.getLeadingOrTrailing(childTree, tokens, True)
                if childTree.getText() != "<INDENT>" and childTree.getText() != "<DEDENT>" and childTree.getText() != "<NEWLINE>":
                    text += childTree.getText()

            else:   
                text += self.createWithHidden(childTree, "", tokens)
                # print(text)

        return text


# testStr ='''def testFunc(var):\n    print("test")\n    if(True and 2==2):\n        print("example")\n        print("test")\n    return test'''  

# print(ConvertToPE(testStr, False, 3).pe)

# shows how to read from json should you wish to upload a dataset in this way
# (file is the destination, data_file is the source)
# file = open("C:/Users/danie/Desktop/Laminar/dispel4py-client/testPEs.py", "a")
# with open("C:/Users/danie/Desktop/Laminar/python_train_1.jsonl") as data_file:
#     for line in data_file:
#         data = json.loads(line)
#         print(data['code'])
#         converted = ConvertToPE(data['code'], False)
#         if converted.pe != None:
#             print(converted.pe)
#             file.write(converted.pe + "\n")
            

