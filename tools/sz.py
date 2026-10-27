import math, sys
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.svgPathPen import SVGPathPen

SRC="/home/kg/Work/omarchy-agentscope/agentscope/fonts/SteelCityComic-Regular.ttf"

def band(pen, path, half):
    P=[path[0]]+list(path)+[path[-1]]
    dense=[]
    for i in range(1,len(P)-2):
        p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
        for j in range(14):
            t=j/14; t2=t*t; t3=t2*t
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

paths={}
paths['v1']=[(150,80),(150,1180),(200,1330),(340,1470),(510,1440),(620,1360),(630,1210),(560,1050),(430,970),(560,890),(770,790),(910,610),(980,410),(890,190),(690,70),(470,10),(300,55),(205,95)]
paths['v2']=[(140,80),(140,1200),(210,1360),(370,1480),(540,1430),(640,1330),(630,1170),(540,1020),(420,940),(600,860),(820,740),(950,540),(960,340),(830,140),(620,30),(400,10),(250,70)]
for name,path in paths.items():
    f=TTFont(SRC); gs=f.getGlyphSet(); pen=TTGlyphPen(gs)
    band(pen,path,86.0)
    g=pen.glyph(); g.recalcBounds(f['glyf'])
    sp=SVGPathPen(gs); 
    # render glyph directly via a temp font
    f['glyf']['germandbls']=g
    import io
    f.save('/tmp/fontwork/t_%s.ttf'%name)
    gs2=TTFont('/tmp/fontwork/t_%s.ttf'%name).getGlyphSet()
    p2=SVGPathPen(gs2); gs2['germandbls'].draw(p2)
    open('/tmp/fontwork/t_%s.svg'%name,'w').write(
      f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1800" viewBox="-200 -100 1400 1800" style="background:#fff"><g transform="translate(0,1600) scale(1,-1)"><path d="{p2.getCommands()}" fill="#111"/></g></svg>')
print("ok")
