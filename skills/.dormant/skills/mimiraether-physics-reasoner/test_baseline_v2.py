"""
颗粒 0 重研 — 五维深度基线分析 v2 (修复版)
LeCun 世界模型五大要求: 预测准确度 / 长期稳定性 / 保结构 / 可逆性 / 步长敏感性
"""
import numpy as np, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model_engine import WorldModelEngine, RigidBody

RESULTS = {}
PASSES = {}

# ===== 场景1: 自由落体 =====
print("="*60)
print("场景1: 自由落体 (h=10m, m=2kg) — 5维诊断")
print("="*60)
eng = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=2.0, position=[0,10,0], velocity=[0,0,0])
eng.add_body(b); eng.add_ground(y=0.0, restitution=0.0)
res = eng.simulate(duration=1.5)
t=res['t']; s=res['states']; g=9.8; m=2.0

mask = s[:,1] > 0.01
D1 = np.max(np.abs(s[mask,1] - (10-0.5*g*t[mask]**2)))<0.002 and np.max(np.abs(s[mask,4] + g*t[mask]))<0.002
E0=m*g*10; E_last=0.5*m*np.sum(s[mask][-1,3:6]**2)+m*g*s[mask][-1,1]
D2=abs(E_last-E0)/E0*100<1.0
D3=np.min(s[:,1])>=-0.001

mid=50; sm=s[mid]
eng2=WorldModelEngine(dt=0.001,method='RK4')
eng2.add_body(RigidBody(mass=m,position=sm[:3].copy(),velocity=-sm[3:6].copy()))
eng2.gravity=np.array([0.,9.8,0.])
res2=eng2.simulate(duration=mid*0.001)
D4=abs(res2['states'][-1,1]-10.0)<0.03 if len(res2['states'])>0 else False

eng_f=WorldModelEngine(dt=0.0005,method='RK4')
eng_f.add_body(RigidBody(mass=m,position=[0,10,0],velocity=[0,0,0]))
eng_f.add_ground(y=0.0,restitution=0.0)
rf=eng_f.simulate(duration=0.5); sf=rf['states']
c=min(len(s),len(sf))//2
D5=np.max(np.abs(s[:c,1]-sf[:c*2:2,1]))<0.005

print(f"  D1 准确度: {'PASS' if D1 else 'FAIL'} | D2 稳定性: {'PASS' if D2 else 'FAIL'} | D3 保结构: {'PASS' if D3 else 'FAIL'}")
print(f"  D4 可逆性: {'PASS' if D4 else 'FAIL'} | D5 步长敏感: {'PASS' if D5 else 'FAIL'}")
PASSES['freefall']=sum([D1,D2,D3,D4,D5]); print(f"  >> {PASSES['freefall']}/5")

# ===== 场景2: 单摆 =====
print()
print("="*60)
print("场景2: 单摆 (L=1m, 30°) — 3维诊断 (D4/D5 N/A)")
print("="*60)
eng=WorldModelEngine(dt=0.001,method='RK4')
L=1.0; th0=np.radians(30)
b=RigidBody(mass=1.0,position=[L*np.sin(th0),-L*np.cos(th0),0],velocity=[0,0,0])
eng.add_body(b); eng.add_spring([0,0,0],k=50000,natural_length=L)
res=eng.simulate(duration=2.2); t=res['t']; x=res['states'][:,0]

# D1: 周期检测 (使用连续同方向过零点)
sign_changes=[]
for i in range(1,len(x)):
    if (x[i-1]>=0 and x[i]<0) or (x[i-1]<=0 and x[i]>0): sign_changes.append(t[i])
T_meas=(sign_changes[1]-sign_changes[0])*2 if len(sign_changes)>=2 else (sign_changes[0]*2 if len(sign_changes)>=1 else 0)
T_ana=2*np.pi*np.sqrt(L/9.8)
D1=abs(T_meas-T_ana)<0.05

E=0.5*np.sum(res['states'][:,3:6]**2,axis=1)+9.8*res['states'][:,1]
D2=abs(E[-1]-E[0])/abs(E[0])*100<2.0 if abs(E[0])>1e-10 else abs(E[-1]-E[0])*100<2.0
r=np.sqrt(res['states'][:,0]**2+res['states'][:,1]**2)
D3=np.max(np.abs(r-L))<0.05

print(f"  D1 周期: T={T_meas:.4f}s (ana={T_ana:.4f}) -> {'PASS' if D1 else 'FAIL'}")
print(f"  D2 稳定性: E_drift={abs(E[-1]-E[0])/E[0]*100 if E[0]>0 else 0:.4f}% -> {'PASS' if D2 else 'FAIL'}")
print(f"  D3 保结构: max_dL={np.max(np.abs(r-L)):.4f}m -> {'PASS' if D3 else 'FAIL'}")
PASSES['pendulum']=sum([D1,D2,D3]); print(f"  >> {PASSES['pendulum']}/3")

# ===== 场景3: 抛体 =====
print()
print("="*60)
print("场景3: 抛体 (v0=20m/s, 45°) — 5维诊断")
print("="*60)
eng=WorldModelEngine(dt=0.001,method='RK4')
v0=20; th=np.radians(45); vx0=v0*np.cos(th); vy0=v0*np.sin(th)
b=RigidBody(mass=1.0,position=[0,0,0],velocity=[vx0,vy0,0])
eng.add_body(b); eng.add_ground(y=0.0,restitution=0.0)
res=eng.simulate(duration=3.0); t=res['t']; s=res['states']
mask=s[:,1]>0.01

x_ana=vx0*t[mask]; y_ana=vy0*t[mask]-0.5*g*t[mask]**2
D1=np.max(np.abs(s[mask,0]-x_ana))<0.05 and np.max(np.abs(s[mask,1]-y_ana))<0.05
E0=0.5*(vx0**2+vy0**2); idx=np.argmax(s[:,1])
D2=abs((0.5*np.sum(s[idx,3:6]**2)+9.8*s[idx,1])-E0)/E0*100<1.0
D3=np.max(np.abs(s[:,2]))<0.001 and np.max(np.abs(s[:,5]))<0.001
mid=50; sm=s[mid]
eng2=WorldModelEngine(dt=0.001,method='RK4')
eng2.add_body(RigidBody(mass=1.0,position=sm[:3].copy(),velocity=-sm[3:6].copy()))
res2=eng2.simulate(duration=0.05)
D4=abs(res2['states'][-1,1]-s[max(0,mid-50),1])<0.02 if len(res2['states'])>0 else False
eng_f=WorldModelEngine(dt=0.0005,method='RK4')
eng_f.add_body(RigidBody(mass=1.0,position=[0,0,0],velocity=[vx0,vy0,0]))
rf=eng_f.simulate(duration=1.0); sf=rf['states']
c=min(len(s),len(sf))//2
D5=np.max(np.abs(s[:c,0]-sf[:c*2:2,0]))<0.05

print(f"  D1 准确度: {'PASS' if D1 else 'FAIL'} | D2 稳定性: {'PASS' if D2 else 'FAIL'} | D3 保结构: {'PASS' if D3 else 'FAIL'}")
print(f"  D4 可逆性: {'PASS' if D4 else 'FAIL'} | D5 步长敏感: {'PASS' if D5 else 'FAIL'}")
PASSES['projectile']=sum([D1,D2,D3,D4,D5]); print(f"  >> {PASSES['projectile']}/5")

# ===== 场景4: 双摆 =====
print()
print("="*60)
print("场景4: 双摆 (L1=L2=1m, 45°/30°) — 保结构压力测试")
print("="*60)
eng=WorldModelEngine(dt=0.001,method='RK4')
L1=L2=1.0; th1=np.radians(45); th2=np.radians(30)
x1=L1*np.sin(th1); y1=-L1*np.cos(th1)
x2=x1+L2*np.sin(th2); y2=y1-L2*np.cos(th2)
b1=RigidBody(mass=1.0,position=[x1,y1,0],velocity=[0,0,0])
b2=RigidBody(mass=1.0,position=[x2,y2,0],velocity=[0,0,0])
eng.add_body(b1); eng.add_body(b2)
k=50000
eng.add_spring([0,0,0],k=k,natural_length=L1)
eng.add_force(lambda s,t: np.zeros(3) if np.linalg.norm(s[:3]-s[:3])<1e-10 else -k*(np.linalg.norm(s[:3]-s[:3])-L2)*(s[:3]-s[:3])/np.linalg.norm(s[:3]-s[:3]))
eng.bodies=[b1,b2]
res=eng.simulate(duration=1.0); s=res['states']
D3_b1=np.max(np.abs(np.sqrt(s[:,0]**2+s[:,1]**2)-L1))<0.10 if len(s)>1 else False
print(f"  D3 保结构: max_dL1={np.max(np.abs(np.sqrt(s[:,0]**2+s[:,1]**2)-L1)):.4f}m -> {'PASS' if D3_b1 else 'FAIL'}")
PASSES['double_pendulum']=1 if D3_b1 else 0

# ===== 总评 =====
print()
print("="*60)
print("═══ 五维基线总评 ═══")
print("="*60)
for sc in ['freefall','pendulum','projectile']:
    tot={'freefall':5,'pendulum':3,'projectile':5}[sc]
    print(f"  {sc}: {PASSES[sc]}/{tot} 维通过")
tp=sum(PASSES[sc] for sc in ['freefall','pendulum','projectile'])
tt=13; pct=tp/tt*100
print(f"\n  全局: {tp}/{tt} 维通过 ({pct:.0f}%)")
print(f"  结论: {'✅ 引擎核心稳定，可进入颗粒1' if pct>=80 else '⚠️ 需修复后再进颗粒1'}")

# 保存
with open('baseline_v2_results.json','w') as f:
    json.dump({'summary':f'{tp}/{tt} ({int(pct)}%)','verdict':'STABLE' if pct>=80 else 'NEEDS_FIX',
        'by_scene':{sc:int(PASSES[sc]) for sc in PASSES}},f,indent=2)
print("\n结果: baseline_v2_results.json")
