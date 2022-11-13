#cilent.py
from urllib.parse import urlparse
from  bitstring import ConstBitStream
import socket, re, sys, base64, os, mmap

def addExtension(file, fileType):
    fileName = file.split('.')
    if fileType == "plain":
        extension = ".txt"
    elif fileType == "octet-stream" or len(fileType) > 8 :
        extension = fileName[-1]
    else:
        extension = "." + fileType

    if fileName[-1] != extension:
        return file + extension
    return file

def singleFileCrawl(tempFile, startContent, header, destinationFile):
    response = ParseHTTPResponse(header)
    file = open(tempFile, 'rb')
    file.seek(startContent)
    contentEncoding =''; transferEncoding = ''; contentType = ''; contentLength = 0
    for key in response.keys():
        if re.match("[Cc]{1}ontent[\s\-_]*[Ee]{1}ncoding", key):
            #If content-encoding found in response
            contentEncoding = contentEncoding + response[key]
        if re.match("[Tt]{1}ransfer[\s\-_]*[Ee]{1}ncoding", key):
            #if transfer encoding found in response
            transferEncoding = transferEncoding + response[key]
        
        #Check if the response has content type and content length
        if re.match("[Cc]{1}ontent[\s\-_]*[Tt]ype", key):
            contentType = contentType + response[key]
        if re.match("[Cc]{1}ontent[\s\-_]*[Ll]{1}ength", key):
            contentLength = int(response[key], 10)
    if contentLength: #If content length > 0, 
        pos = startContent + contentLength
        with open("currentFileBinData.dat", 'wb') as tempWrite:
            data = file.read(contentLength)
            tempWrite.write(data)
        fileType = contentType.split('/')
        destination = addExtension(destinationFile, fileType[-1])
        MakeFile("currentFileBinData.dat", destination, contentType, contentEncoding)
    elif transferEncoding == "chunked":
        bufferLength = ChunkedDecoding(tempFile, startContent, "currentFileBinData.dat")
        pos = startContent + bufferLength
        fileType = contentType.split('/')
        destination = addExtension(destinationFile, fileType[-1])
        MakeFile("currentFileBinData.dat", destination, contentType, contentEncoding)
    return pos

def parseUrl(url):
    #parse url in cases when the url's scheme is not provided 
    # #(that urlparse method will not work properly)
    if '://' in url:
        return urlparse(url)
    else:
        url = 'http://' + url
        return urlparse(url)

def ParseHTTPResponse(headers):
    """ This function is based on the answer from this website: 
    https://stackoverflow.com/questions/10832974/python-regular-expression-for-http-request-header """
    headers = headers.splitlines()
    firstLine = headers.pop(0)
    (protocol, statuscode, statustext) = firstLine.split(' ')
    d = {'Protocol' : protocol, 'Status-Code' : statuscode, 'Status-Text' : statustext}
    for h in headers:
        h = h.split(': ')
        if len(h) < 2:
            continue
        field=h[0]
        value= h[1]
        d[field] = value
    return d

def MakeFile(rawFile, destinationFile, ContentType, ContentEncoding):
    
    """This function will generate the actual type (text or binary, after header removed and chunk decoded)
    from the raw Unicode text file based on the ContentType and ContentEncoding argument"""
    type = ContentType.split("/")
    if type[0] == "text":
        file = open(rawFile, 'rb+')
        with open(destinationFile, 'w') as wr:
            while True:
                line = file.read().decode()
                if not line:
                    break
                wr.write(line)
        file.close()
    else : #type[0] == "application" or "image":
        #If the file is an binary file, write destination file by binary stream instead of unicode string
                #'='*(blah blah) string is the padding required for base64, base32 and base16 encoding
                #Source:
                if not ContentEncoding:
                    #If the content is not encoded for transfer,trying to decode will result in an error
                    #The binary string will be put directly without being decoded
                    file = open(rawFile, 'rb')
                    with open(destinationFile, 'wb') as wr:
                        while True:
                            line = file.read()
                            if not line:
                                break
                            wr.write(line)
                    file.close()
                else: #Encoded data
                    file = open(rawFile, 'rb')
                    with open(destinationFile, 'wb') as wr:
                        while True:
                            line = file.read().decode()
                            if not line:
                                break
                    if ContentEncoding == "base64":
                        wr.write(base64.b64decode(line + '='*(-len(line)%4)))
                    elif ContentEncoding == "base32":
                        wr.write(base64.b32decode(line + '='*(-len(line)%8)))
                    elif ContentEncoding == "base16":
                        wr.write(base64.b16decode(line + '='*(-len(line)%16)))
                    file.close()
    print("File ", destinationFile, "is successfully downloaded")



def ReadSocket(url, tempFile, maxRecursiveLevel):
    parse = parseUrl(string)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((parse.netloc, 80))

    #Send a GET request and save the data received in a temporaray file
    request = "GET " + parse.path + " HTTP/1.1\r\nHost: " + parse.netloc+ "\r\n\r\n"
    openFile = open(tempFile, 'wb+')
    s.send(request.encode())
    stringData = b''
    while True:
        data = s.recv(32768)
        if not data:
            break
        openFile.write(data)
    #Find the header in the temp file
    openFile.seek(0)
    data = openFile.read()
    #header = stringData.split(b'\r\n\r\n')[0]
    fileMap  = mmap.mmap(openFile.fileno(), 0)

    #Find the first header end index
    headerEndIndex = []
    headerEndIndex.append(fileMap.find(b'\r\n\r\n'))
    while True:
        headerEnd = fileMap.find(b'\r\n\r\n', headerEndIndex[len(headerEndIndex)-1]+1, fileMap.size()-3)
        if headerEnd == -1:
            break
        else:
            headerEndIndex.append(headerEnd)
    #Find b"/r/n/r/n" in the temporary file

    if headerEndIndex:
        header = fileMap[:headerEndIndex[0]].decode()
    print(header,"\n")
    parseName = parse.path.split('/')
    if not parse.path: #Root request, save file as html
        mainFileOpen = open("index.html", 'wt')
        for line in openFile:
            if not line:
                break
            mainFileOpen.write(line.decode())
        mainFileOpen.close()
    else:
        if parseName[-1]:#Single file, no recursive to crawl url
            #From the current openFile pointer in the file, read the rest of the file (the content)
            singleFileCrawl(tempFile, headerEndIndex[0]+4, header, parseName[-1])
        else:
            for line in openFile:
                if not line:
                    break
                inlink = re.findall("<a href=\"(.+?\..+?)\">", line)
            #Not complete
    #Close and delete temporary file
    
    #os.remove("resultTruncate.txt")
    openFile.close()
    s.close()

def ChunkedDecoding(tempFileName, startContent, dataFile):
    
    #Function to decode chunked data from the start of the current data block of the temporary binary file
    #til the end of the chunked data
    #Export to the dataFile file which contain the text encoded (content, not transfer encoded) data
    # which will be used to generate to actual file
    dataFile = open(dataFile, 'w+')
    ContentLength = 0; pos = startContent
    with open(tempFileName, 'rb+') as file:
        mapTemp = mmap.mmap(file.fileno(), 0)
        mapTemp.seek(startContent)
        while True:
            #Read the first line in each pair of lines
            #to know how many characters to pick up in the second line
            line = mapTemp.readline()
            if not line:
                raise EOFError("unexpected blank line")
               
            #Change the hexadecimal string of to a readable dataChunkLength
            #variable in decimal, and write new data to the actual file
            ContentLength += len(line)
            dataChunkLength = int(line.decode(), 16)
            if not dataChunkLength:
                break
            if dataChunkLength > 0:
                data = mapTemp.read(dataChunkLength)
                ContentLength += len(data)
                dataFile.write(data.decode())
            #Since the file.read method didn't get rid of the newline character(s)
            # in the second line, use readline method again
            # to get rid of those character(s).
            data = mapTemp.read(2)
            ContentLength += len(data)
            if data != b'\r\n' and data != b'\n\n':
                raise EOFError("Unexpected character after chunk", data)
            
            #Break if final byte has been reached, also save the current file pointer
            if dataChunkLength == 0:
                break
    pos += ContentLength
    dataFile.close()
    return pos
        
            


#string = "web.stanford.edu/dept/its/support/techtraining/techbriefing-media/Intro_Net_91407.ppt"
string = "http://anglesharp.azurewebsites.net/Chunked"
ReadSocket(string, "test.txt", 1)
""" print(1)
parse = parseUrl(string)
# print(ParsingDomain(string),"\n")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((parse.netloc, 80))
request = "GET " + parse.path + " HTTP/1.1\r\nHost: " + parse.netloc+ "\r\n\r\n"
s.send(request.encode())
data = s.recv(10000)
print(data,"\n")
stringData = data.decode('utf-8')
match = re.findall("<a href=\"(.+?\..+?)\">", stringData)
stringData = stringData.split('\r\n\r\n\r\n')
#print(stringData)
res = ParseHTTPResponse(stringData[0])
print(match,"\n")
print(res) """
