import urllib.request,urllib.parse,sys,json
def q(query,out):
    req=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'MetroGuideBCN-prototype/0.1 (personal project)'})
    d=urllib.request.urlopen(req,timeout=300).read()
    open(out,'wb').write(d); return json.loads(d)
if __name__=='__main__':
    print(len(q(open(sys.argv[1]).read(),sys.argv[2])['elements']))
