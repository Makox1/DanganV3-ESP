"""Reconstruye estilos de interfaz usando glifos de las texturas originales."""
import json
import unicodedata
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def renderizar(texto, nombre, color):
    raiz = Path(__file__).resolve().parents[1] / 'imagenes/fuentes'
    info = json.loads((raiz / (nombre + '.json')).read_text(encoding='utf-8'))
    atlas = Image.open(raiz / (nombre + '.png')).convert('L')
    glifos = info['glifos']
    lienzo = Image.new('L', (max(1,len(texto)*72), 80))
    x = 0
    for letra in texto:
        if letra == ' ':
            x += info['espacio']; continue
        base = unicodedata.normalize('NFD', letra)[0]
        invertida = letra == '¡'
        if invertida: base = '!'
        if base not in glifos:
            raise ValueError('Glifo ausente en %s: %s' % (nombre, letra))
        g = glifos[base]
        im = atlas.crop(tuple(g['caja']))
        if invertida: im = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        y = g['y'] + 12
        lienzo.paste(im,(x,y))
        if letra != base and not invertida:
            d=ImageDraw.Draw(lienzo)
            if letra.lower() in 'áéíóú':
                d.line((x+im.width//2-2,y-4,x+im.width//2+4,y-9),fill=255,width=3)
            elif letra.lower()=='ñ':
                d.line((x+2,y-5,x+6,y-8,x+10,y-5,x+14,y-8),fill=255,width=2)
        x += im.width + info['separacion']
    caja=lienzo.getbbox()
    if caja is None: raise ValueError('Rotulo vacio')
    mascara=lienzo.crop(caja)
    salida=Image.new('RGBA',mascara.size,tuple(color)+(0,));salida.putalpha(mascara)
    return salida


def acabado(texto, original, estilo):
    """Aplica desgaste y contorno despues del escalado, a resolucion final."""
    a=np.array(original)
    mascara=texto.getchannel('A')
    if estilo.get('desgaste_original'):
        visibles=a[a[...,3]>128,:3]
        oscura=len(visibles)>0 and np.median(visibles)<128
        blancos=(a[...,3]>128) if oscura else ((a[...,:3].mean(axis=2)>180)&(a[...,3]>128))
        lleno=Image.fromarray((blancos*255).astype('uint8'))
        # Los poros del original se conservan como una textura sobre la tinta nueva.
        cerrado=lleno.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        poros=np.maximum(np.array(cerrado).astype(int)-np.array(lleno).astype(int),0).astype('uint8')
        poros=Image.fromarray(poros).resize(texto.size,Image.Resampling.NEAREST)
        nueva=np.array(mascara).astype(int)-np.array(poros).astype(int)
        mascara=Image.fromarray(np.clip(nueva,0,255).astype('uint8'))
    texto=texto.copy();texto.putalpha(mascara)
    borde=int(estilo.get('contorno_final',0))
    if borde:
        margen=borde+1
        resultado=Image.new('RGBA',(texto.width+2*margen,texto.height+2*margen))
        alfa=Image.new('L',resultado.size);alfa.paste(mascara,(margen,margen))
        alfa=alfa.filter(ImageFilter.MaxFilter(borde*2+1))
        base=Image.new('RGBA',resultado.size,tuple(estilo.get('color_contorno',[0,0,0]))+(0,))
        base.putalpha(alfa)
        if estilo.get('desgaste_original'):
            original_alfa=original.getchannel('A')
            fuera=Image.fromarray(np.maximum(np.array(original_alfa).astype(int)-np.array(lleno.filter(ImageFilter.MaxFilter(9))).astype(int),0).astype('uint8'))
            fuera=fuera.resize(base.size,Image.Resampling.NEAREST)
            base.putalpha(Image.fromarray(np.maximum(np.array(base.getchannel('A')),np.array(fuera))))
        base.alpha_composite(texto,(margen,margen));return base
    if estilo.get('sombra'):
        radio=int(estilo['sombra']);margen=radio*2
        base=Image.new('RGBA',(texto.width+2*margen,texto.height+2*margen))
        alfa=Image.new('L',base.size);alfa.paste(mascara,(margen,margen))
        alfa=alfa.filter(ImageFilter.GaussianBlur(radio)).point(lambda v:min(255,v*2))
        base.putalpha(alfa);base.alpha_composite(texto,(margen,margen));return base
    return texto


def letras_variables(texto, estilo):
    """Iniciales blancas y letras decrecientes como los encabezados de preparacion."""
    from PIL import ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/'+estilo['fuente'],160)
    out=Image.new('RGBA',(1000,180));x=0
    for i,ch in enumerate(texto):
        box=font.getbbox(ch);m=Image.new('L',(box[2]-box[0]+4,box[3]-box[1]+4))
        ImageDraw.Draw(m).text((2-box[0],2-box[1]),ch,font=font,fill=255)
        h=round(estilo['alto']*(1-.38*i/max(1,len(texto)-1)))
        w=max(1,round(m.width*h/m.height));m=m.resize((w,h),Image.Resampling.LANCZOS)
        color=[255,255,255] if i<2 else estilo['color']
        im=Image.new('RGBA',m.size,tuple(color)+(0,));im.putalpha(m)
        im=im.rotate((i-1)*-1.2,Image.Resampling.BICUBIC,expand=True)
        out.alpha_composite(im,(x,round(estilo['alto']-h)));x+=w+1
    return out.crop(out.getbbox())
