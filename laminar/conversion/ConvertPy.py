from antlr4 import *
from laminar.aroma.PythonLexer import PythonLexer
from laminar.aroma.PythonParser import PythonParser
from antlr4.tree.Tree import TerminalNodeImpl
import json

# for reading in as string

# from VisitorInterp import VisitorInterp

# translated from facebook aroma ConvertJava.java


# this might actually be more efficient as we are not building a stack
# and we theoretically are not multi threading so no need to be thread safe

# suspected bug with pythonLexer.py produced by antlr,
# in other language (ie Java) it is interpreted to include null for names that do not have a literal conversion
# pythonLexer.py does not, and without them, the names do not match the appropriate token values
expectedLiteralNames = [None, None, None, None, None, None, "'False'", "'await'", "'else'", "'import'", 
		"'pass'", "'None'", "'break'", "'except'", "'in'", "'raise'", "'True'", 
		"'class'", "'finally'", "'is'", "'return'", "'and'", "'continue'", "'for'", 
		"'lambda'", "'try'", "'as'", "'def'", "'from'", "'nonlocal'", "'while'", 
		"'assert'", "'del'", "'global'", "'not'", "'with'", "'async'", "'elif'", 
		"'if'", "'or'", "'yield'", "'('", "'['", None, "')'", "']'", None, "'.'", 
		"':'", "','", "';'", "'+'", "'-'", "'*'", "'/'", "'|'", "'&'", "'<'", 
		"'>'", "'='", "'%'", "'=='", "'!='", "'<='", "'>='", "'~'", "'^'", "'<<'", 
		"'>>'", "'**'", "'+='", "'-='", "'*='", "'/='", "'%='", "'&='", "'|='", 
		"'^='", "'<<='", "'>>='", "'**='", "'//'", "'//='", "'@'", "'@='", "'->'", 
		"'...'", "':='", "'!'"]
#retrieved from lexer
symbolicNames = []
identifiersRuleNames = [
            "IDENTIFIER",
            "localVar",
            "CHAR_LITERAL",
            "STRING_LITERAL",
            "BOOL_LITERAL",
            "NULL_LITERAL",
            "DECIMAL_INTEGER",
            "HEX_INTEGER",
            "OCT_INTEGER",
            "BINARY_INTEGER",
            "FLOAT_NUMBER",
            "NAME"]
localVarContexts = ["atom"]


class ConvertPyToAST:
    

    # input: either a file path, or a raw string of the desired code to be converted
    # isFile, states if the input should be treated as a file or raw string
    def __init__(self, input, isFile):
        self.stackDepth = 0
        self.MAX_DEPTH = 1000
        self.childHasLeaf = False
        self.ruleNames = []
        self.beginLine = 0
        self.endLine = 0
        self.totalMethods = 0
        self.thisFileName = ""
        self.thisClassName = ""
        self.thisMethodName = ""
        self.outputFile = ""
        self.result = []

        if isFile:
            input_stream = FileStream(input)
        else:
            input_stream = InputStream(input)


        lexer = PythonLexer(input_stream)
        vocab = lexer.symbolicNames

        stream = CommonTokenStream(lexer)
        parser = PythonParser(stream)
        # print(parser)
        tree = parser.file_input()

        self.setRuleNames(parser)
        self.setSymbolicNames(lexer)
        fullAST = self.getSerializedTree(tree, stream)
        # if no methods, then we take the whole input as the AST
        if(self.totalMethods == 0):
            self.dumpMethodAST("function_def_raw", fullAST, True)
            # print(fullAST)



    # Python Lexer does not provide the appropriate Vocabulary class
    # this provides the functionality of the java python lexer of
    # taking either the literal name or symbolic name
    def getDisplayName(self, tokenType):
        global expectedLiteralNames, symbolicNames
        if(tokenType < len(expectedLiteralNames) and expectedLiteralNames[tokenType] != None):
            return expectedLiteralNames[tokenType]
        return symbolicNames[tokenType]

    def setSymbolicNames(self, lexer):
        global symbolicNames
        symbolicNames = lexer.symbolicNames

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
            
            return ""
        if(isBefore):
            ws = tokens.getHiddenTokensToLeft(lastIndexOfToken, HIDDEN)
        elif(lastIndexOfToken >= 0 or lastIndexOfToken == -2):
            ws = tokens.getHiddenTokensToRight(lastIndexOfToken, HIDDEN)
        if(ws != None):
            for wst in ws:
                
                text += wst.text
        return text
    def dumpMethodAST(self, thisRuleName, simpleTree, fullAST=False):
        # only write the functions to the JSON file, to avoid duplication
        if (thisRuleName == "function_def_raw" or fullAST == True):
            # print(simpleTree)
            if(len(simpleTree) == 2):
                try:
                    simpleTree = json.dumps(simpleTree[1])
                except:
                    return 
            tmp = {}
            tmp["path"] = self.thisFileName
            tmp["class"] = self.thisClassName
            tmp["method"] = self.thisMethodName
            tmp["beginline"] = self.beginLine
            tmp["endline"] = self.endLine
            tmp["ast"] = simpleTree


            # append to results list
            self.result.append(tmp)


            # option to write to file
            # print("writing to file")
            # print(tmp)
            # f = open(outputFile, "a")
            # json.dump(tmp, f)
            # # f.write(str(tmp))
            # f.close()


            self.totalMethods += 1

    def setClassName(self, thisRuleName, tree, i):
        if(thisRuleName == "class_def_raw" and i > 0):
            prev = tree.getChild(i - 1)
            curr = tree.getChild(i)

            # (class and name should be leaf nodes)
            if(prev is TerminalNodeImpl and curr is TerminalNodeImpl
                and prev.getText() == "class"):
                thisToken = curr.getSymbol()
                ruleName = self.getDisplayName(thisToken.type)

                # set the class name
                if(ruleName == "NAME"):
                    self.thisClassName = thisToken.getText()

    # convert the AST into a json AST for the similarity comparision
    def getSerializedTree(self, tree, tokens: CommonTokenStream):
        self.stackDepth += 1
        numChildren = tree.getChildCount()
        hasLeaf = False
        # if we are at the end of a leaf, we go no further
        if(numChildren == 0 or self.stackDepth > self.MAX_DEPTH):
            self.childHasLeaf = False
            self.stackDepth -= 1
            return None

        thisRuleName = self.getRuleName(tree)
        oldClassName = None
        oldMethodName = None
        oldBeginLine = 0


        # set the class name
        if(thisRuleName == "class_def_raw"):
            oldClassName = self.thisClassName

        # set the function name
        if (thisRuleName == "function_def_raw"):
            oldMethodName = self.thisMethodName
            self.thisMethodName = tree.getChild(1).getText()

        simpleTree = []
        simpleTree.append("")

        # could use some form of string builder if it was really necessary
        text = ""
    
        for i in range(numChildren):
            childTree = tree.getChild(i)
            # is a leaf
            if(isinstance(childTree, TerminalNodeImpl)):
                s = childTree.getText()
                if(not s == "<EOF>"):

                    thisToken = childTree.getSymbol()
                    ruleName = self.getDisplayName(thisToken.type)
                    # print(ruleName)

                    # get leading and trailing chars (ie indentation / line breaks etc)
                    ws1 = self.getLeadingOrTrailing(childTree, tokens, True)
                    ws2 = self.getLeadingOrTrailing(childTree, tokens, False)
                    tok = {}
                    # print(s)
                    tok["token"] = s
                    tok["leading"] = ws1
                    tok["trailing"] = ws2
                    
                    isLeaf = False

                    if(ruleName in identifiersRuleNames):
                        if(thisRuleName in localVarContexts):
                            tok["var"] = True
                            
                        isLeaf = True
                        text += "#"
                        hasLeaf = True
                        self.setClassName(thisRuleName, tree, i)
                    else:
                        isLeaf = False
                        text += s
                    
                    if isLeaf: tok["leaf"] = isLeaf
                    tok["line"] = thisToken.line
                    simpleTree.append(tok)
                
            # not a leaf
            else:
                child = self.getSerializedTree(childTree, tokens)
                if(child != None and len(child) > 0):
                    if(len(child) == 2):
                        simpleTree.append(child[1])
                        text += child[0]
                        hasLeaf = hasLeaf or self.childHasLeaf
                        
                    elif(not self.childHasLeaf):
                        text += child[0]
                        for j in range(1, len(child)):
                            simpleTree.append(child[j])
                    
                    else:
                        text += "#"
                        hasLeaf = True
                        simpleTree.append(child)

        simpleTree.insert(0, text)
        self.childHasLeaf = hasLeaf

        self.dumpMethodAST(thisRuleName, simpleTree)

        # revert the class name
        if(thisRuleName == "class_def_raw"):
            self.thisClassName = oldClassName

        # revert the function name
        if (thisRuleName == "function_def_raw"):
            self.thisMethodName = oldMethodName
            self.beginLine = oldBeginLine

        self.stackDepth -= 1
        return simpleTree


