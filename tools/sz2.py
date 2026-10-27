import math
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.svgPathPen import SVGPathPen
SRC="/home/kg/Work/omarchy-agentscope/agentscope/fonts/SteelCityComic-Regular.ttf"

def band(pen, path, half, close_ends=True):
    P=[path[0]]+list(path)+[path[-1]]
    dense=[]
    for i in range(1,len(P)-2):
        p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
        for j in range(16):
            t=j/16; t2=t*t; t3=t2*t
            x=0.5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y=0.5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            dense.append((x,y))
    dense.append(P[-2])
    nrm=[]
    for i,p in enumerate(dense):
        a=dense[max(0,i-1)]; b=dense[min(len(dense)-1,i+1)]
        dx,dy=b[0]-a[0],b[1]-a[1]; L=math.hypot(dx,dy) or 1
        nrm.append((-dy/L,dx/L))
    left=[(p[0]+n[0]*half,p[1]+n[1]*half) for p,n in zip(dense,nrm)]
    right=[(p[0]-n[0]*half,p[1]-n[1]*half) for p,n in zip(dense,nrm)]
    pen.moveTo(left[0])
    for p in left[1:]: pen.lineTo(p)
    for p in reversed(right): pen.lineTo(p)
    pen.closePath()

# Variante A: Stamm + oberer Haken + untere Schleife (drei Konturen)
def varA(pen):
    band(pen,[(150,120),(150,1150),(150,1420)],86)                          # Stamm
    band(pen,[(150,1400),(330,1500),(480,1430),(500,1280),(400,1120),(300,1060)],80)  # Haken
    band(pen,[(300,1060),(470,1000),(650,860),(720,600),(680,320),(520,120),(320,70),(220,140)],84)  # Schleife

# Variante B: wie A, aber Stamm laenger und Haken offener
def varB(pen):
    band(pen,[(150,90),(150,1150),(160,1430)],88)
    band(pen,[(160,1430),(360,1520),(520,1420),(520,1260),(400,1090),(290,1030)],78)
    band(pen,[(290,1030),(470,980),(660,850),(730,590),(680,300),(510,110),(300,60),(205,120)],82)

# Variante C: ein einziger offener Umriss (kein Band), klassische ss-Outline
def varC(pen):
    O=[(66,60),(66,1000),(80,1300),(170,1450),(330,1500),(470,1460),(560,1350),(560,1220),
       (500,1100),(380,1030),(300,1000),(430,960),(620,860),(760,650),(800,420),(700,180),
       (520,50),(340,20),(200,70),(150,110),(150,80),(120,20)]
    pen.moveTo(O[0]); [pen.lineTo(p) for p in O[1:]]; pen.closePath()

for name,fn in [('A',varA),('B',varB),('C',varC)]:
    f=TTFont(SRC); gs=f.getGlyphSet(); pen=TTGlyphPen(gs); fn(pen)
    f['glyf']['germandbls']=pen.glyph(); f['glyf']['germandbls'].recalcBounds(f['glyf'])
    f.save('/tmp/fontwork/z_%s.ttf'%name)
    gs2=TTFont('/tmp/fontwork/z_%s.ttf'%name).getGlyphSet()
    sp=SVGPathPen(gs2); gs2['germandbls'].draw(sp)
    open('/tmp/fontwork/z_%s.svg'%name,'w').write(
      f'<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="1800" viewBox="-150 -100 1300 1800" style="background:#fff"><g transform="translate(0,1600) scale(1,-1)"><path d="{sp.getCommands()}" fill="#111"/></g></svg>')
print("ok")
