def real_row_resample(X,n,rng):
    idx=rng.integers(0,len(X),size=n)
    return X[idx].copy(),{"sample_indices_preview":idx[:100].tolist()}

def real_contiguous_block(X,n,rng):
    if n>=len(X): s=0; Y=X.copy()
    else: s=int(rng.integers(0,len(X)-n+1)); Y=X[s:s+n].copy()
    return Y,{"base_start":s,"base_length":len(Y)}

def independent_marginals(X,n,rng):
    Y=np.empty((n,X.shape[1]))
    for j in range(X.shape[1]): Y[:,j]=X[rng.integers(0,len(X),size=n),j]
    return Y,{}

def column_shuffle(X,n,rng):
    if n>=len(X): s=0; base=X.copy()
    else: s=int(rng.integers(0,len(X)-n+1)); base=X[s:s+n].copy()
    Y=base.copy()
    for j in range(Y.shape[1]): rng.shuffle(Y[:,j])
    return Y,{"base_start":s,"base_length":len(base),"base_block":base}

def hurdle_iid(X,n,rng):
    Y=np.empty((n,X.shape[1]))
    for j in range(X.shape[1]):
        col=X[:,j]; nz=col[col!=0]; p0=float(np.mean(col==0)); z=rng.random(n)<p0
        vals=nz[rng.integers(0,len(nz),size=n)] if len(nz) else np.zeros(n)
        vals=np.asarray(vals,float); vals[z]=0; Y[:,j]=vals
    return Y,{}

def independent_stitch(X,n,rng,chunk=60):
    Y=np.empty((n,X.shape[1]))
    for j in range(X.shape[1]):
        pieces=[];remain=n
        while remain>0:
            k=min(chunk,remain); s=0 if len(X)<=k else int(rng.integers(0,len(X)-k+1))
            pieces.append(X[s:s+k,j]); remain-=k
        Y[:,j]=np.concatenate(pieces)
    return Y,{"chunk_rows":chunk}

def shared_stitch(X,n,rng,chunk=60):
    pieces=[];starts=[];remain=n
    while remain>0:
        k=min(chunk,remain); s=0 if len(X)<=k else int(rng.integers(0,len(X)-k+1))
        pieces.append(X[s:s+k]); starts.append(s); remain-=k
    return np.vstack(pieces),{"chunk_rows":chunk,"chunk_starts_preview":starts[:100]}

def learned_gmm_overlay(X,n,rng):
    base,_=hurdle_iid(X,n,rng)
    idx=[feature_index[c] for c in LEARNED_SCOPE if c in feature_index]
    if not idx:return base,{"learned_scope_size":0}
    Z=X[:,idx]; scaler=StandardScaler().fit(Z); Zs=scaler.transform(Z)
    k=min(8,max(1,len(Zs)//1000))
    gmm=GaussianMixture(n_components=k,covariance_type="diag",random_state=int(rng.integers(0,2**31-1)),max_iter=150,reg_covar=1e-5).fit(Zs)
    samp,_=gmm.sample(n); vals=scaler.inverse_transform(samp); vals=np.clip(vals,Z.min(axis=0),Z.max(axis=0)); base[:,idx]=vals
    return base,{"learned_scope_size":len(idx),"components":k}

def learned_latent_var_overlay(X,n,rng):
    base,_=shared_stitch(X,n,rng)
    idx=[feature_index[c] for c in LEARNED_SCOPE if c in feature_index]
    if not idx:return base,{"learned_scope_size":0}
    Z=X[:,idx]; scaler=StandardScaler().fit(Z); Zs=scaler.transform(Z)
    ncomp=min(16,Zs.shape[1],max(2,Zs.shape[0]//500)); pca=PCA(n_components=ncomp,random_state=0).fit(Zs); L=pca.transform(Zs)
    lags=[1,5,30]; maxlag=max(lags); XX=[];YY=[]
    for t in range(maxlag,len(L)):
        XX.append(np.concatenate([L[t-l] for l in lags])); YY.append(L[t])
    reg=Ridge(alpha=1.0).fit(np.asarray(XX),np.asarray(YY))
    hist=[L[max(0,len(L)-maxlag+i)].copy() for i in range(maxlag)]; out=np.empty((n,ncomp))
    for t in range(n):
        feat=np.concatenate([hist[-l] for l in lags]); cur=reg.predict(feat.reshape(1,-1))[0]+rng.normal(0,0.05,size=ncomp)
        out[t]=cur; hist.append(cur)
    vals=scaler.inverse_transform(pca.inverse_transform(out)); vals=np.clip(vals,Z.min(axis=0),Z.max(axis=0)); base[:,idx]=vals
    return base,{"learned_scope_size":len(idx),"latent_components":ncomp}

def generic_health(reference,syn):
    tr_std=np.std(reference,axis=0); sy_std=np.std(syn,axis=0); variable=tr_std>1e-9
    vf=float(np.mean(sy_std[variable]>1e-9)) if variable.any() else 1.0
    support=float(np.mean((syn<reference.min(axis=0))|(syn>reference.max(axis=0))))
    a=np.abs(np.mean(syn==0,axis=0)-np.mean(reference==0,axis=0))
    return {"finite":bool(np.isfinite(syn).all()),"variable_fraction":vf,"support_violation":support,
            "activity_error_mean":float(np.mean(a)),"activity_error_p95":float(np.quantile(a,.95)),"activity_error_max":float(np.max(a))}

def exact_column_multiset_equal(A,B):
    if A.shape!=B.shape:return False,np.inf
    mx=0.0
    for j in range(A.shape[1]):
        a=np.sort(A[:,j]); b=np.sort(B[:,j]); d=float(np.max(np.abs(a-b))) if len(a) else 0.0; mx=max(mx,d)
        if not np.array_equal(a,b):return False,mx
    return True,mx

def validate_contract(source,Xtr,syn,meta):
    contract=SOURCE_CONTRACT[source]; base={"contract":contract}
    if not np.isfinite(syn).all():
        return {**base,"contract_state":"Execution-Invalid","contract_valid":False,"promotion_permission":"DIAGNOSTIC_ONLY","reason":"non-finite output"}
    if contract=="REAL_SAMPLING_ANCHOR":
        support=float(np.mean((syn<Xtr.min(axis=0))|(syn>Xtr.max(axis=0)))); ok=bool(support==0 and syn.shape[1]==Xtr.shape[1])
        return {**base,"support_violation":support,"contract_state":"Anchor-Valid" if ok else "Anchor-Invalid","contract_valid":ok,"promotion_permission":"ANCHOR_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    if contract=="REAL_CHRONOLOGICAL_ANCHOR":
        s=int(meta["base_start"]); n=int(meta["base_length"]); exact=bool(np.array_equal(syn,Xtr[s:s+n])); ok=bool(exact and n==len(syn))
        return {**base,"base_start":s,"base_length":n,"exact_contiguous_block":exact,"contract_state":"Anchor-Valid" if ok else "Anchor-Invalid","contract_valid":ok,"promotion_permission":"ANCHOR_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    if contract=="MARGINAL_DESTRUCTION_MECHANISM":
        h=generic_health(Xtr,syn); ok=bool(h["support_violation"]<=1e-12 and h["variable_fraction"]>=0.95 and h["activity_error_mean"]<=0.03 and h["activity_error_max"]<=0.10)
        return {**base,**h,"contract_state":"Mechanism-Valid" if ok else "Mechanism-Invalid","contract_valid":ok,"promotion_permission":"MECHANISM_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    if contract=="COLUMN_SHUFFLE_INVARIANT":
        B=meta["base_block"]; multiset,maxdiff=exact_column_multiset_equal(B,syn)
        zr=float(np.max(np.abs(np.mean(B==0,axis=0)-np.mean(syn==0,axis=0)))); std=float(np.max(np.abs(np.std(B,axis=0)-np.std(syn,axis=0))))
        same=float(np.mean([np.mean(B[:,j]==syn[:,j]) for j in range(B.shape[1])])); destroyed=bool(same<0.99)
        # Exact column-multiset equality already guarantees identical marginal values; the recomputed std difference is retained only as an audit diagnostic because floating-point reduction can introduce sub-nanoscopic rounding differences.
        ok=bool(multiset and zr<=1e-12 and destroyed)
        return {**base,"column_multiset_exact":multiset,"column_multiset_max_abs_diff":maxdiff,"zero_rate_max_abs_diff":zr,"std_max_abs_diff":std,"mean_same_position_fraction":same,"alignment_destroyed":destroyed,"contract_state":"Mechanism-Valid" if ok else "Mechanism-Invalid","contract_valid":ok,"promotion_permission":"MECHANISM_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    if contract in {"TRANSPARENT_OUTPUT_HEALTH","TRANSPARENT_STITCH_HEALTH"}:
        h=generic_health(Xtr,syn); ok=bool(h["variable_fraction"]>=0.95 and h["support_violation"]<=1e-12 and h["activity_error_mean"]<=0.05 and h["activity_error_p95"]<=0.15 and h["activity_error_max"]<=0.30)
        return {**base,**h,"contract_state":"Mechanism-Valid" if ok else "Mechanism-Invalid","contract_valid":ok,"promotion_permission":"MECHANISM_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    if contract=="LEARNED_FIT_HEALTH":
        h=generic_health(Xtr,syn); fh=RULES["learned_fit_health"]
        ok=bool(h["variable_fraction"]>=fh["variable_fraction_min"] and h["support_violation"]<=fh["support_violation_max"] and h["activity_error_mean"]<=fh["activity_error_mean_max"] and h["activity_error_p95"]<=fh["activity_error_p95_max"] and h["activity_error_max"]<=fh["activity_error_max_max"])
        return {**base,**h,"contract_state":"Fit-Valid" if ok else "Fit-Invalid","contract_valid":ok,"promotion_permission":"GENERATOR_EVIDENCE" if ok else "DIAGNOSTIC_ONLY"}
    raise RuntimeError(contract)
