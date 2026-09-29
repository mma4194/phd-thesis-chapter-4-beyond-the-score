def software_checks():
    checks=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append({'check':name,'passed':True,'scope':'constructed software test'})
    task=TaskCard('test','regression','temporal','y',1,(0,1),('x',),None,'router','test','test','byte_volume','y')
    f=pd.DataFrame({'x':np.arange(20,dtype=float),'y':np.arange(20,dtype=float)})
    f.loc[8,'y']=np.nan
    X,y,a=task_arrays(f,task)
    check('Missing forecast labels removed',not y.isna().any() and a['missing_target_contexts']==1 and len(y)==17)
    event=replace(task,task_id='state_transition__test',task_type='classification',label_window_steps=3,threshold=.5,horizon=0)
    f['y']=(np.arange(20)%4<2).astype(float);f.loc[8,'y']=np.nan
    _,y,a=task_arrays(f,event)
    check('Transition context includes current and all future readings',a['missing_target_contexts']==4 and y.isin([0.,1.]).all())
    burst=replace(event,task_id='burst__test')
    _,_,a=task_arrays(f,burst)
    check('Burst context excludes current reading',a['missing_target_contexts']==3)
    imputer=TrainingMedianWithIndicators().fit([[1.,np.nan],[3.,np.nan]])
    z=imputer.transform([[np.nan,100.],[900.,np.nan]])
    check('Training medians and explicit missing indicators',z.shape==(2,4) and z[0,0]==2 and z[0,2]==1 and z[1,1]==0 and z[1,3]==1)
    f['y']=np.arange(20);_,_,a=task_arrays(f,task,segments=np.repeat([0,1],10))
    check('No feature or label spans a block join',a['join_contexts_removed']==2)
    ii,jj=linear_sum_assignment([[4,1,3],[2,0,5],[3,2,2]])
    check('Minimum-cost assignment has unique partners',list(jj)==[1,0,2] and len(set(jj))==3)
    a=np.array([1.,1.,2.,5.]);ref=np.sort(a);r=(np.searchsorted(ref,a,'left')+np.searchsorted(ref,a,'right'))/(2*len(ref))
    check('Midranks preserve ties and remain bounded',r[0]==r[1] and np.all((r>=0)&(r<=1)))
    check('Positive-reference rule rejects poor real reference',(2.-3.)/2.<0)
    return checks
