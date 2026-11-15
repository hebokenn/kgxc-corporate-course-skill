#!/usr/bin/env python3
"""Original KGXC kinetic-showcase score; no existing music or samples."""
import argparse
import math
import wave
from pathlib import Path
import numpy as np

RATE=48000
BPM=120
BEAT=60/BPM
SEED=6098120

def hz(midi): return 440*2**((midi-69)/12)
def filt(x, f, kind):
    """First-order RC/FFT magnitude filter on already short sound objects."""
    freq=np.fft.rfftfreq(len(x),1/RATE)
    low=1/np.sqrt(1+(freq/f)**2)
    fac=low if kind=='low' else (freq/f)*low
    return np.fft.irfft(np.fft.rfft(x)*fac,n=len(x))
def smoothenv(t, length, a=.025, r=.08):
    return np.sin(np.minimum(1,t/a)*np.pi/2)**2*np.sin(np.minimum(1,np.maximum(0,length-t)/r)*np.pi/2)**2

def make_score(duration,markers,breaks,path):
    rng=np.random.default_rng(SEED)
    n=int(round(duration*RATE))
    main=np.zeros((n,2),np.float32)
    beat_bus=np.zeros((n,2),np.float32)
    kickpoints=[]
    def time(d):
        return np.arange(max(2,int(round(RATE*d))),dtype=np.float64)/RATE
    def place(dest, snd, at, vol, pan=0, spread=0):
        k=round(at*RATE)
        if k>=n or k<0: return
        m=min(len(snd),n-k)
        gain=math.pi*(pan+1)/4
        dest[k:k+m,0]+=snd[:m]*(math.cos(gain)*vol)
        dest[k:k+m,1]+=snd[:m]*(math.sin(gain)*vol)
        if spread:
            u=k+round(spread*RATE); m=min(len(snd),n-u)
            if m>0:dest[u:u+m,1]+=.16*snd[:m]*vol
    def noise(t):
        return rng.standard_normal(len(t))
    t=time(.39)
    kick=(np.sin(2*np.pi*(46*t+3.35*(1-np.exp(-t/.030))))*np.exp(-t/.090)
          +.18*np.sin(2*np.pi*(64*t+2.3*(1-np.exp(-t/.010))))*np.exp(-t/.027))
    kick*=np.minimum(1,t/.0012)
    kick+=.12*filt(noise(t),950,'high')*np.exp(-t/.006)*np.minimum(1,t/.0005)
    k_short=kick[:int(.19*RATE)]*smoothenv(t[:int(.19*RATE)],.19,a=.001,r=.04)
    def snare():
        t=time(.26); n=filt(noise(t),1350,'high'); n=filt(n,7600,'low')
        bursts=sum(np.exp(-np.maximum(t-s,0)/d)*(t>s) for s,d in [(0,.012),(.012,.014),(.027,.021),(.038,.048)])
        return .55*n*bursts + .28*np.sin(2*np.pi*185*t)*np.exp(-t/.047)*np.minimum(1,t/.001)
    sn, snb=snare(),snare()
    def hat(d):
        t=time(d); x=filt(noise(t),6400,'high'); x=filt(x,12300,'low')
        return x*np.exp(-t/(d*.24))*np.minimum(1,t/.001)*smoothenv(t,d,a=.001,r=.009)
    hat_s,hat_o,hat_t=hat(.084),hat(.23),hat(.041)
    def tom(m):
        t=time(.25); f=hz(m)
        return (.85*np.sin(2*np.pi*(f*t+1.9*(1-np.exp(-t/.026))))+.16*np.sin(2*np.pi*1.49*f*t))*np.exp(-t/.065)*smoothenv(t,.25,a=.002,r=.02)
    toms=[tom(m) for m in (49,43,38)]
    def bass(m,d):
        t=time(d);p=2*np.pi*hz(m)*t
        x=np.sin(p)+.32*np.sin(2*p+.2)+.12*np.sin(3*p)+.07*np.sin(5*p)*np.exp(-t/.10)
        return np.tanh(.74*x)*smoothenv(t,d,a=.008,r=.045)*(.71+.29*np.exp(-t/.18))
    def pluck(m,d,bright=1):
        t=time(d); p=2*np.pi*hz(m)*t
        x=(np.sin(p+.24*np.sin(2*p)*np.exp(-t/.06))+.32*np.sin(2.001*p)
           +bright*.22*np.sin(3.994*p+.8)*np.exp(-t/.055)+.10*np.sin(5.02*p)*np.exp(-t/.031))
        return x*np.exp(-t/.19)*smoothenv(t,d,a=.004,r=.055)
    def pad(m,d,detune):
        t=time(d); p=2*np.pi*hz(m)*t
        return (.62*np.sin(p)+.36*np.sin(p*(1+detune)+.8)+.17*np.sin(2*p+.35)
                +.08*np.sin(3*p+.2))*smoothenv(t,d,a=.17,r=.22)*(.88+.12*np.sin(2*np.pi*.30*t))
    def rise(dest, at, d=.48, vol=.10):
        t=time(d); x=filt(filt(noise(t),1100,'high'),9200,'low')
        frac=t/d
        place(dest,x*(frac**2)*smoothenv(t,d,a=.02,r=.018),at,vol,.17,.010)
        place(dest,.31*np.sin(2*np.pi*(77*t+55*t*t))*frac**2*smoothenv(t,d,a=.05,r=.012),at,vol*.55,-.35)
    def impact(at,fin=False):
        t=time(.92)
        x=(.62*np.sin(2*np.pi*(34*t+3.3*(1-np.exp(-t/.08))))*np.exp(-t/.20)
           +.25*filt(noise(t),340,'low')*np.exp(-t/.18))
        x*=smoothenv(t,.92,a=.005,r=.1)
        place(beat_bus,x,at,.35 if fin else .26)
        cym=hat(.53)
        place(beat_bus,cym,at,.24 if fin else .19,-.28,.013)
    # E minor > C major > G major > D add9; original recurring rhythmic figures.
    chords=([52,55,59,62],[48,55,59,64],[43,50,55,59],[50,57,62,64])
    roots=(40,36,43,38)
    motifs=((76,71,74,79),(76,67,71,74),(74,71,79,81),(76,69,74,78))
    cells=((0,.75,1.50,2,2.75,3.50),(0,1,1.75,2.50,3,3.5),(0,.5,1.75,2,2.75,3.75))
    mode=lambda s: any(a-1e-6<=s<b-1e-6 for a,b in breaks)
    active=[]
    for bar in range(math.ceil(duration/2)):
        at=bar*2.0; i=bar%4; bd=mode(at); out=(at>=duration-4)
        density=.72 if bar<2 else 1.
        if out: density*=.87
        active+=([at] if not bd else [])
        for j,m in enumerate(chords[i]):
            place(main,pad(m,2.30,.0026 if j%2 else -.0026),at,.071*(.85 if bd else 1),(-.44,-.17,.18,.43)[j])
        riff=motifs[i]
        for off,j in (((.5,0),(1.75,1),(2.5,2),(3.75,3)) if bd else
                      ((.25,0),(1,1),(1.75,2),(2.5,3),(3.25,1),(3.75,2))):
            note=riff[j]; v=.13 if bd else .115*density
            if bar in (0,1):v*=1.10
            t0=at+off*BEAT
            pattern=pluck(note,.35,1.06)
            place(main,pattern,t0,v,(-.30,.25,-.15,.38)[j],.022)
            place(main,pattern,t0+.1875,v*.21,.49)
        if bd:
            for off in (0,2.5):
                place(main,bass(roots[i],.68),at+off*BEAT,.16)
            for off in (1.,2.75,3.5):
                place(beat_bus,hat_t,at+off*BEAT,.12,-.35)
            if bar%2:
                place(beat_bus,toms[1],at+3.5*BEAT,.20,.19)
            continue
        pattern=((0,1.5,2,2.75),(0,.75,2,3.5),(0,1.5,2,3.25),(0,1.25,2.75,3.5))[i]
        if bar==0:pattern=(0,2,3.5)
        for off in pattern:
            when=at+off*BEAT; kickpoints.append(when)
            place(beat_bus,kick if off in (0,2) else k_short,when,.70*density*(1 if off in (0,2) else .88))
        for off in (1,3):
            place(beat_bus,sn,at+off*BEAT,.39*density,-.035,.008)
            place(beat_bus,snb,at+off*BEAT+.006,.19*density,.26)
        for k in range(8):
            when=at+.25*k+(.008 if k%2 else 0)
            place(beat_bus,hat_s if k not in (3,7) else hat_o,when,
                  (.14,.20,.12,.24,.13,.19,.12,.24)[k]*density,(-.43,.39)[k%2],.009)
        if bar>=4 and bar%2:
            for off in (2.75,3.25,3.50,3.75):
                place(beat_bus,hat_t,at+off*BEAT,.12,.43 if int(off*4)%2 else -.33)
        for k,off in enumerate(cells[bar%3]):
            m=roots[i]+(12 if k==4 and bar%2 else 0)
            dur=.21 if (k%2 or off>=3.2) else .32
            place(main,bass(m,dur),at+off*BEAT,.37*density)
    # Accent the moment each clip demonstrates its action, not just the cut.
    tc=time(.084)
    rim=(.62*np.sin(2*np.pi*1420*tc)+.29*np.sin(2*np.pi*2134*tc))*np.exp(-tc/.011)*np.minimum(tc/.001,1)
    for j,sec in enumerate(range(5,40,2)):
        place(beat_bus,rim,sec,.13 if j%3 else .18,(-.24,.19)[j%2])
    for sec in markers:
        if sec>=duration: continue
        if sec>=.47: rise(beat_bus,sec-.47,.47,.21)
        if sec>=.38 and not mode(sec+.03):
            for a, off in enumerate((.375,.250,.125)):
                place(beat_bus,toms[a],sec-off,(.21,.27,.34)[a],(-.34,.22,0)[a])
        impact(sec,sec==markers[-1])
    # Rhythm follows moving information: macro ducking helps the kick stay clean.
    duck=np.ones(n,np.float32)
    q=time(.24); env=1-.45*np.exp(-q/.085)
    for at in kickpoints:
        k=int(at*RATE);m=min(len(env),n-k)
        duck[k:k+m]=np.minimum(duck[k:k+m],env[:m])
    music=np.tanh(.95*(main*duck[:,None]+beat_bus))
    tail=min(11040,n)
    music[-tail:]*=np.sin(np.linspace(np.pi/2,0,tail,dtype=np.float32))[:,None]**2
    peak=float(np.max(np.abs(music))); music*=.89/max(peak,1e-5)
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(RATE)
        out.writeframes((32767*music).astype('<i2').tobytes())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--duration',type=float,default=64)
    p.add_argument('--hits',default='0,4,16,28,42,48,54,60')
    p.add_argument('--breaks',default='40:42,62:64')
    a=p.parse_args()
    markers=sorted(set(float(x) for x in a.hits.split(',') if x.strip()))
    breaks=[tuple(map(float,x.split(':'))) for x in a.breaks.split(',') if x.strip()]
    make_score(a.duration,markers,breaks,a.output)

if __name__=='__main__':main()
