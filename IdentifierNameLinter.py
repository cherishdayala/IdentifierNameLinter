import re
from io import TextIOWrapper

import enchant
import wordninja
from github import Github
from github.ContentFile import ContentFile
from tree_sitter import Language, Parser


def userInput():
    repoLink = input("Enter public GitHub repo link: ")
    fileExtension = input("Enter file extension (.py, .js, .go, or .rb): ")
    language = input("Enter programming language (python, javascript, go, or ruby): ")
    output1Path = input("Enter filepath for output 1: ")
    output2Path = input("Enter filepath for output 2: ")
    return repoLink, fileExtension, language, output1Path, output2Path

# Create a parser for the specified language
def createParser(language: str):
    Language.build_library(
        'build/my-languages.so',
        [
            'vendor/tree-sitter-python',
            'vendor/tree-sitter-javascript',
            'vendor/tree-sitter-go',
            'vendor/tree-sitter-ruby'
        ]
    )
    PY_LANGUAGE = Language('build/my-languages.so', 'python')
    JS_LANGUAGE = Language('build/my-languages.so', 'javascript')
    GO_LANGUAGE = Language('build/my-languages.so', 'go')
    RUBY_LANGUAGE = Language('build/my-languages.so', 'ruby')

    parser = Parser()
    if language.lower() == 'python':
        parser.set_language(PY_LANGUAGE)
        queryLanguage = PY_LANGUAGE
    elif language.lower() == 'javascript':
        parser.set_language(JS_LANGUAGE)
        queryLanguage = JS_LANGUAGE
    elif language.lower() == 'go':
        parser.set_language(GO_LANGUAGE)
        queryLanguage = GO_LANGUAGE
    elif language.lower() == 'ruby':
        parser.set_language(RUBY_LANGUAGE)
        queryLanguage = RUBY_LANGUAGE
    
    return parser, queryLanguage

# Get files of specified repo
def getRepoContents(repoLink: str):
    github = Github()
    splitRepoLink = repoLink.split("github.com/")
    repoFullName = splitRepoLink[1]
    repo = github.get_repo(repoFullName)
    contents = repo.get_contents("")
    return repo, contents

# Parse file and return dictionary of identifier:locations
def parseFile(parser: Parser, file_content: ContentFile, language: Language, identifierInstances: dict[bytes, dict]):
    tree = parser.parse(file_content.decoded_content)
    query = language.query("(identifier) @identifier")
    captures = query.captures(tree.root_node)
    for node in captures:
        identifier = file_content.decoded_content[node[0].start_byte:node[0].end_byte]
        if (identifier not in identifierInstances.keys()):
            identifierInstances.update({identifier: {file_content.path: [node[0].start_point]}})
        elif (file_content.path not in identifierInstances.get(identifier).keys()):
            identifierInstances.get(identifier).update({file_content.path: [node[0].start_point]})
        else:
            identifierInstances.get(identifier).get(file_content.path).append(node[0].start_point)

    return identifierInstances

# Print identifiers to specified file. If analyze is set, only prints rule violators and the rules they violate, otherwise, prints all identifiers
def printIdentifiers(outputFile: TextIOWrapper, identifierInstances: dict[bytes, dict], analyze: bool):
    for identifier in identifierInstances.keys():
        if (analyze):
            violationReport = analyzeIdentifier(identifier.decode())
            if (violationReport == ""):
                continue
        
        outputFile.write(str(identifier.decode()) + ": found in file(s)\n")
        for file in identifierInstances.get(identifier).keys():
            outputFile.write("\t" + file + " at lines: ")
            for location in identifierInstances.get(identifier).get(file):
                outputFile.write(str(location[0] + 1) + ":" + str(location[1] + 1) + ", ")
            outputFile.truncate(outputFile.tell() - 2)
            outputFile.seek(outputFile.tell() - 2)
            outputFile.write('\n')

        if (analyze):
            outputFile.write("\t" + violationReport + "\n")

        outputFile.write('\n\n')

# Generates string of all rules that identifier violates
def analyzeIdentifier(identifier: str):
    validShortIdentifiers = ["c", "d", "e", "g", "i", "in", "inOut", "j", "k", "m", "n", "o", "out", "t", "x", "y", "z"]
    if identifier in validShortIdentifiers:
        return ""

    violationReport = "Violates: "
    wordList = splitIdentifier(identifier)
    if capitalisationAnomaly(identifier):
        violationReport += "Capitalisation Anomaly, "
    if consecutiveUnderscores(identifier):
        violationReport += "Consecutive Underscores, "
    if dictionaryViolation(wordList):
        violationReport += "Dictionary Words, "
    if len(wordList) > 4:
        violationReport += "Excessive Words, "
    if externalUnderscores(identifier):
        violationReport += "External Underscores, "    
    if len(identifier) > 20:
        violationReport += "Long Identifier Name, "
    if namingConventionAnomaly(wordList):
        violationReport += "Naming Convention Anomaly, "
    if len(wordList) < 2 or len(wordList) > 4:
        violationReport += "Number of Words, "
    if numericIdentifierName(wordList):
        violationReport += "Numeric Identifier Name, "
    if len(identifier) < 8:
        violationReport += "Short Identifier Name, "

    if violationReport == "Violates: ":
        return ""
    violationReport = violationReport[:-2]
    return violationReport

# Split identifier into words on underscores or capital letters
def splitIdentifier(identifier: str):
    if '_' in identifier:
        wordList = identifier.split('_')
    elif identifier.isupper() or identifier.islower():
        return [identifier]
    else:
        wordList = re.findall('[a-zA-Z][^A-Z]*', identifier)
    while "" in wordList:
        wordList.remove("")
    return wordList 

# Check list of words for capitalisation
def capitalisationAnomaly(identifier: str):
    if '_' not in identifier:
        englishWordList = wordninja.split(identifier)
        if ((identifier.islower() or identifier.isupper()) and len(englishWordList) > 1 and not all(word.isnumeric() for word in englishWordList[1:])):
            return True
    else:
        wordList = identifier.split('_')
        for word in wordList:
            if (len(word) <= 1):
                continue
            if (not word.isupper() and not word[1:].islower()):
                return True
    return False     

# Check identifier for consecutive underscores
def consecutiveUnderscores(identifier: str):
    pattern = '^.*__.*$'
    return re.match(pattern, identifier)

# Check if identifier is composed of words found in dictionary or common abbreviations/acronyms
def dictionaryViolation(wordList: list[str]):
    englishDictionary = enchant.Dict("en_US")
    for word in wordList:
        if not englishDictionary.check(word):
            return True
    return False 

# Check if identifier has leading or trailing underscores
def externalUnderscores(identifier: str):
    pattern = '(^.*_$)|(^_.*$)'
    return re.match(pattern, identifier)

# Check if naming convention within identifier is consistent
def namingConventionAnomaly(wordList: list[str]):
    if (len(wordList) <= 1):
        return False
    firstWordConvention = namingConvention(wordList[0])
    for i in range(1, len(wordList)):
        currentWordConvention = namingConvention(wordList[i])
        if (firstWordConvention != currentWordConvention and currentWordConvention != "NUMERIC"):
            if (not (firstWordConvention == "LOWER" and currentWordConvention != "CAMEL")):
                return True
    return False

def namingConvention(word: str):
    if (word.isupper()):
        return "UPPER"
    if (word.islower()):
        return "LOWER"
    if (word.isnumeric()):
        return "NUMERIC"
    if (word[0].isupper() and word[1:].islower()):
        return "CAMEL"
    return "INVALID"

# Check if identifier is numeric or only contains numeric words
def numericIdentifierName(wordList: list[str]):
    numericWords = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", 
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "fourty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million", "billion", "trillion"]
    lowerWordList = [word.lower() for word in wordList]
    if (all(word.isnumeric() for word in wordList) or all(word in numericWords for word in lowerWordList)):
        return True
    return False

def main():
    repoLink, fileExtension, language, output1Path, output2Path = userInput()
    repo, contents = getRepoContents(repoLink)
    parser, queryLanguage = createParser(language)
    output1File = open(output1Path, "w")    
    output2File = open(output2Path, "w")
    
    identifierInstances = dict()
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents.extend(repo.get_contents(file_content.path))
        elif file_content.name.lower().endswith(fileExtension):
            identifierInstances = parseFile(parser, file_content, queryLanguage, identifierInstances)            
            
    printIdentifiers(output1File, identifierInstances, False)
    printIdentifiers(output2File, identifierInstances, True)

    output1File.close()
    output2File.close()    

if __name__ == '__main__':
    main()
