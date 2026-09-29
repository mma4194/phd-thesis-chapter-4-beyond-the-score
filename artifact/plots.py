from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def create(audit):
 p=Path(audit.out)/'figures';p.mkdir(exist_ok=True)
 datasets=[('Residential: supported same-time groups',audit.tables['residential_summary_replay'].query("matching == 'balanced_observed' and period == 'future'"),'ci_lo','ci_hi'),('TON_IoT: supported forecasting tasks',audit.tables['toniot_utility'].query("regime == 'primary' and period == 'future'"),'lo','hi')]
 fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
 for ax,(title,d,lo,hi) in zip(axs,datasets):
  d=d.sort_values('loss_ratio');y=np.arange(len(d));v=d.loss_ratio.to_numpy()
  ax.errorbar(v,y,xerr=np.array([v-d[lo].to_numpy(),d[hi].to_numpy()-v]),fmt='o',color='#235a8e',capsize=3)
  ax.set_yticks(y,[s.replace('_',' ') for s in d.source],fontsize=8);ax.invert_yaxis();ax.axvline(1.1,color='#555555',ls='--',lw=1);ax.set_xscale('log');ax.set_title(title,fontsize=10);ax.set_xlabel('Synthetic / real loss; conditional 95% interval');ax.grid(axis='x',alpha=.2)
 fig.savefig(p/'future_relative_utility.pdf');fig.savefig(p/'future_relative_utility.png',dpi=180);plt.close(fig)
 return p

def paper_figures(audit):
 """Regenerate numerical figure content; layouts are portable artifact layouts."""
 import pandas as pd
 import textwrap
 from .common import ROOT
 out=Path(audit.out)/'figures';out.mkdir(exist_ok=True)
 def save(fig,name):
  fig.savefig(out/(name+'.pdf'),bbox_inches='tight');fig.savefig(out/(name+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)
 # Figure 4: both periods, using the supported primary scope only.
 d=audit.tables['residential_summary_replay'].query("matching == 'balanced_observed'")
 order=d[d.period=='future'].sort_values('loss_ratio').source.tolist();fig,ax=plt.subplots(figsize=(10,5.5),layout='constrained')
 for period,offset,color in [('same_period',-.12,'#235a8e'),('future',.12,'#be6b22')]:
  x=d[d.period==period].set_index('source').loc[order];v=x.loss_ratio.to_numpy();ax.errorbar(v,np.arange(len(x))+offset,xerr=np.array([v-x.ci_lo.to_numpy(),x.ci_hi.to_numpy()-v]),fmt='o',color=color,capsize=3,label=period.replace('_',' '))
 ax.set_yticks(np.arange(len(order)),[s.replace('_',' ') for s in order],fontsize=8);ax.invert_yaxis();ax.set_xscale('log');ax.axvline(1,color='#777777',ls='--');ax.axvline(1.1,color='#777777',ls=':');ax.set_xlabel('Synthetic / real loss; conditional 95% seed interval');ax.set_title('Residential: three supported same-time groups');ax.legend();save(fig,'figure_04_residential_utility')
 d.to_csv(out/'figure_04_data.csv',index=False)
 # Figure 2: the ten registered targeted responses from primitive seed curves.
 curves=pd.read_csv(ROOT/'reference/controlled/table_controlled_instrument_ladder_seed_level.csv');spec=audit.tables['metric_responses'];fig,axs=plt.subplots(4,3,figsize=(12,11),layout='constrained')
 for ax,row in zip(axs.flat,spec.itertuples()):
  x=curves[curves.perturbation==row.target_perturbation].groupby('severity')[row.instrument].mean();ax.plot(x.index,x.values,'o-',color='#235a8e');ax.set_title('\n'.join(textwrap.wrap(row.instrument.replace('_',' '),25)),fontsize=9);ax.set_xlabel(row.target_perturbation+' severity');ax.set_ylabel('Mean response');ax.grid(alpha=.2)
 for ax in list(axs.flat)[len(spec):]:ax.set_visible(False)
 save(fig,'figure_02_metric_responses');curves.to_csv(out/'figure_02_data.csv',index=False)
 # Figure 3: qualification matrix recomputed from primitive P0 losses.
 q=audit.tables['residential_P0'].query("arm == 'balanced_observed' and clipped").copy()
 fields=['eligible','identity_ok','relative_ok','reference_viable','order_ok','final_rule_licensed']
 labels=['Estimable','Identity','Relative','Reference skill','Order','Licensed']
 from matplotlib.colors import ListedColormap
 fig,(ax,point)=plt.subplots(2,1,figsize=(11,10),gridspec_kw={'height_ratios':[9,1.8]},layout='constrained')
 ax.imshow(q[fields].astype(int).to_numpy(),cmap=ListedColormap(['#e1e6eb','#235a8e']),vmin=0,vmax=1,aspect='auto')
 ax.set_xticks(range(len(fields)),labels,rotation=25,ha='right')
 ax.set_yticks(range(len(q)),q.capability.str.replace('_',' ',regex=False),fontsize=8)
 ax.set_title('Residential qualification: fixed balanced-observed plan (blue = pass)')
 lo=float(q.loc[q.capability.eq('forecast|protocol_other'),'resample_minus_block_log_lo'].iloc[0])
 point.axvline(0,color='#888888',lw=1);point.axvline(np.log(1.05),color='#be6b22',ls='--')
 point.scatter([lo],[0],color='#235a8e',s=35);point.set_xlim(-.002,.065);point.set_yticks([])
 point.set_xlabel('Lower endpoint of protocol-other forecast order effect (log loss ratio)')
 point.text(lo,.12,f'{lo:.3f}',ha='center');point.text(np.log(1.05),-.12,'log(1.05) = 0.04879',ha='center',fontsize=8)
 point.set_ylim(-.3,.3);point.set_title('The positive lower endpoint remains below the retained 5% minimum; this point is not a full interval.',fontsize=9)
 save(fig,'figure_03_task_qualification');q.to_csv(out/'figure_03_data.csv',index=False)
 # Supplementary Figure S1: paired period effects, with the original seed intervals.
 t=audit.tables['residential_transfer_replay'].query("matching == 'balanced_observed'").sort_values('gap')
 fig,ax=plt.subplots(figsize=(10,5),layout='constrained');v=t.gap.to_numpy()
 ax.errorbar(v,np.arange(len(t)),xerr=np.array([v-t.ci_lo.to_numpy(),t.ci_hi.to_numpy()-v]),fmt='o',capsize=3,color='#235a8e')
 ax.set_yticks(np.arange(len(t)),t.source.str.replace('_',' ',regex=False),fontsize=8);ax.axvline(0,color='#777777',ls='--')
 ax.set_xlabel('Future minus same-period log loss ratio; conditional 95% seed interval')
 ax.set_title('Residential period contrast: three supported same-time groups')
 save(fig,'figure_s01_period_contrasts');t.to_csv(out/'figure_s01_data.csv',index=False)
 # Figure 5: all reported ablations, counting accepted cases whose development label withholds permission.
 d=audit.tables['controlled_ablation_counts'];fig,ax=plt.subplots(figsize=(10,5),layout='constrained');ax.barh(np.arange(len(d)),d.accepted_withheld,color='#235a8e');ax.set_yticks(np.arange(len(d)),d.ablation.str.replace('_',' ',regex=False),fontsize=8);ax.set_xlabel('Accepted among 52 cases with a withheld development label');ax.set_title('Controlled development cases: stage ablations');ax.invert_yaxis();save(fig,'figure_05_development_ablations');d.to_csv(out/'figure_05_data.csv',index=False)
 # Figure 6: separate classifier resolution, source validity and utility panels.
 r=ROOT/'reference/toniot';p0=pd.read_csv(r/'primary_P0_C2ST.csv').groupby('scope').AUC.max();src=pd.read_csv(r/'source_checks.csv').groupby('source').contract_valid.agg(['sum','size']);u=audit.tables['toniot_utility'].query("regime == 'primary' and period == 'future'").sort_values('loss_ratio')
 fig,axs=plt.subplots(3,1,figsize=(10,12),layout='constrained');axs[0].barh(p0.index.str.replace('_',' '),p0.values,color='#235a8e');axs[0].set_xlim(.98,1.001);axs[0].axvline(.995,ls=':',color='#555555');axs[0].set_xlabel('Maximum P0 AUC (axis starts at 0.98)')
 axs[1].barh(src.index.str.replace('_',' '),src['sum'],color='#235a8e');axs[1].barh(src.index.str.replace('_',' '),src['size']-src['sum'],left=src['sum'],color='#d1d5db');axs[1].set_xlabel('Valid (blue) and invalid (grey) source runs out of eight')
 vals=u.loss_ratio.to_numpy();axs[2].errorbar(vals,u.source.str.replace('_',' '),xerr=np.array([vals-u.lo.to_numpy(),u.hi.to_numpy()-vals]),fmt='o',capsize=3,color='#235a8e');axs[2].axvline(1,ls='--',color='#777777');axs[2].axvline(1.1,ls=':',color='#777777');axs[2].set_xscale('log');axs[2].set_xlabel('Future synthetic / real loss; conditional 95% seed interval')
 for ax in axs:ax.tick_params(axis='y',labelsize=8)
 save(fig,'figure_06_toniot_evaluation');return out
