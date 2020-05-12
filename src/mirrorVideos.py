#!/usr/bin/python3
import json, os.path, sys, getopt, pprint, subprocess,shlex, urllib3
from pprint import pprint

# XXX - TODO:
# - Better Meta Data Save
# 	- listID
#	- channelID
#	- channelTitle

class googleAPI:
    url = ''
    apiKey = ''
    maxCount = 0

    def __init__(self,  apiKey, maxCount = 10):
        self.apiKey = apiKey
        self.maxCount = maxCount


    # forUsername={UserName}
    # id={id}
    def channels(self, url):
        self.url = "https://www.googleapis.com/youtube/v3/channels?part=contentDetails&" + url + "&key=" + self.apiKey


    # maxResults={max rez}&playlistId={listId}&pageToken={pageToken}
    def playlistItems(self, url):
        self.url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&" + url + \
            "&maxResults=" + str(self.maxCount) + \
            "&key=" + self.apiKey


    def jsondata(self):
        http = urllib3.PoolManager()
        resp = http.request("GET", self.url)  # XXX - Handle error

        return json.loads(resp.data)


class ytChannelMirror:
    gAPI = False
    mapName = ''
    error = False
    mapData = { }
    listId = ''
    channelId = ''
    skipDownload = False
    fetchFormat = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    fetchDir  = '/opt/yt/download'
    fetchFile = '%(uploader)s-%(title)s.%(ext)s'

    def __init__(self, mapName, apiKey):
        self.mapName = mapName
        self.listId = os.path.splitext(os.path.basename(mapName))[0]
        self.channelId = self.listId

        self.gAPI = googleAPI(apiKey)
        self.gAPI.channels("forUsername=" + self.listId)
        data = self.gAPI.jsondata()

        if data['pageInfo']['totalResults']:
            self.listId = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        else:
            self.gAPI.channels("id=" + self.listId)
            data = self.gAPI.jsondata()

            if data['pageInfo']['totalResults']:
                self.listId = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']


    def ChannelInfo(self):
        channelTitle = ''

        for value in self.mapData:
            if 'channelTitle' in self.mapData[value]:
                channelTitle = self.mapData[value]['channelTitle']

        print("Title: ", channelTitle, "(" + self.channelId , "/" , self.listId + ")")


    def setSkipDownload(self):
        self.skipDownload = True


    def processVideoList(self, data,map,nextToken):
        for value in data:
            videoId = value['snippet']['resourceId']['videoId']
            if videoId not in map:
                print("New Entry: " + videoId)
                map[videoId] = {
                  "title": value['snippet']['title'],
                  "publishedAt": value['snippet']['publishedAt'],
                  "channelTitle": value['snippet']['channelTitle'],
                  "fetched": self.fetch(videoId) 
                } 
            else:
               nextToken = ''
        return nextToken, map


    def fetch(self, code):
        if self.skipDownload == True:
            return True

        args = shlex.split('/usr/bin/youtube-dl -f \'' + self.fetchFormat + '\' -o ' + self.fetchDir + '/' + self.fetchFile + ' https://www.youtube.com/watch?v=' + code)
        print("D/L: ", args)
        p = subprocess.Popen(args)
        d = p.communicate()

        if (p.returncode == 0):
            return True

        print("Failure Return: ", p.returncode)
        return False

    def videosFromListId(self, pageToken = ''):
        url = "&playlistId=" + self.listId
        if pageToken:
            url = url + "&pageToken=" + pageToken

        self.gAPI.playlistItems(url)
        data = self.gAPI.jsondata()

        if 'nextPageToken' in data:
            return data['nextPageToken'], data['items']
        else:
            return '', data['items']


    def loadMap(self):
        if os.path.isfile(self.mapName):
            with open(self.mapName, 'r') as infile:
                map = json.load(infile)
        else:
            map = {}

        self.mapData = map

    def saveMap(self):
        with open(self.mapName, 'w') as outfile:
            json.dump(self.mapData, outfile)


    def process(self):
        if self.error == True:
           return

        map = self.mapData

        nextToken, list = self.videosFromListId('')
        nextToken, map = self.processVideoList(list, map, nextToken)

        while nextToken:
            nextToken, list = self.videosFromListId(nextToken)
            nextToken, map = self.processVideoList(list, map, nextToken)

        for value in map:
            if 'fetched' in map[value]:
               fetched = map[value]['fetched']
            else:
               fetched = False; 

            if not fetched:
                map[value]['fetched'] = self.fetch(value)

        self.mapData = map


    def displayMap(self):
        if self.error == True:
           return

        for value in self.mapData:
            if self.mapData[value]['fetched'] == True:
                print("[X] ", end = '')
            else:
                print("[ ] ", end = '')
            print(value, end = ' ')
            print(self.mapData[value]['publishedAt'], end = ' ')
            print(self.mapData[value]['title'])


    def toggleDownloadStatus(self, valueDownload):
         if  valueDownload in self.mapData:
             if self.mapData[valueDownload]['fetched'] == True:
                 self.mapData[valueDownload]['fetched'] = False
                 display = "Not Downloaded"
             else:
                 self.mapData[valueDownload]['fetched'] = True
                 display = "Downloaded"

             print("Set to", display, "-", self.mapData[valueDownload]['title'])
         else:
             print("Key not found in map.")



def main(argv):
    mapName = ''
    valueDownload = ''
    apiKey=""

    SHOW_HELP = False
    DISPLAY_MAP = False
    skipDownload = False

    try:
        opts, args = getopt.getopt(argv, "a:t:hlm:sv")
    except getopt.GetoptError:
        SHOW_HELP = True
    else:
      for opt, arg in opts:
          if opt == '-h':
              SHOW_HELP = True
          elif opt == '-m':
              mapName = arg
          elif opt == '-s':
              skipDownload = True
          elif opt == '-a':
              apiKey = arg
          elif opt == '-t':
              valueDownload = arg
          elif opt == '-l':
              DISPLAY_MAP = True
    if not mapName:
       print("Error: No map file defined.")
       SHOW_HELP = True
    if apiKey == '':
       print("Error: No Google API Key defined.")
       SHOW_HELP = True

    if SHOW_HELP:
        print('mirrorVideo -a <apikey> -m <mapFile> [options]')
        print("	-a <apikey>		-- Set Youttube API key [required]")
        print("	-t <value>		-- Toggle download status")
        print("	-l 			-- List vidoes in Map")
        print("	-m <mapFile>		-- Map File for history [required]")
        print("	-s            		-- Set all items to Download") 
        print("	-h            		-- This silly help text")
        sys.exit(2)

    ytChan = ytChannelMirror(mapName, apiKey)
    ytChan.loadMap()
    ytChan.ChannelInfo()

    if DISPLAY_MAP == True:
        ytChan.displayMap() 
    elif valueDownload != '':
        ytChan.toggleDownloadStatus(valueDownload)
        ytChan.saveMap()
    else:
        if skipDownload == True:
            ytChan.setSkipDownload()
        ytChan.process()
        ytChan.saveMap()


if __name__ == "__main__":
    main(sys.argv[1:])
