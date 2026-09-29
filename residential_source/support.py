def separate_values(a,b,review_class):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if not len(a) or not len(b):return {'available':False},None,None
    assert np.isfinite(a).all() and np.isfinite(b).all()
    unique=np.unique(a);outside=(b<a.min())|(b>a.max())
    unseen=~np.isin(b,unique);inside_unseen=(~outside)&unseen
    old=outside | (unseen if len(unique)<=32 else False)
    fractional=b!=np.rint(b)
    resolved=review_class in {'continuous','discrete_count'}
    applied=review_class
    if review_class=='continuous':new=outside
    elif review_class=='discrete_count' and np.all(a==np.rint(a)):
        new=outside | (fractional if len(unique)<=32 else False)
    else:
        new=old;resolved=False
        if review_class=='discrete_count':applied='unresolved_noninteger_training_representation'
    info={
      'available':True,'train_observed':len(a),'generated_observed':len(b),
      'train_unique_count':len(unique),'train_min':float(a.min()),'train_max':float(a.max()),
      'out_of_train_range_count':int(outside.sum()),'unseen_in_range_count':int(inside_unseen.sum()),
      'noninteger_generated_count':int(fractional.sum()),'integer_membership_replacement_applied':bool(review_class=='discrete_count' and resolved and len(unique)<=32),'old_violation_count':int(old.sum()),
      'revised_violation_count':int(new.sum()),'old_violation_fraction':float(old.mean()),
      'revised_violation_fraction':float(new.mean()),'applied_class':applied,
      'definition_resolved_for_this_rule':resolved,
      'outside_examples':np.unique(b[outside])[:8].tolist(),
      'unseen_inside_examples':np.unique(b[inside_unseen])[:8].tolist()}
    return info,old,new

def check_output(train,prepared,out,source,notes):
    scoped=N['source_health'](train,prepared,out,source,notes)
    revised_fractions=[];separated=[]
    # Reapply the previous explicitly scoped membership correction, with no new field classifications.
    for r in scoped['features']:
        c=r['feature'];value=r.get('support_violation_fraction',0.)
        if c in DEFINITIONS and r['observed_comparison']:
            a=train[c].to_numpy(float)[N['observed'](train,c)];b=out[c].to_numpy(float)[N['observed'](out,c)]
            detail,_,_=separate_values(a,b,DEFINITIONS[c]['review_class']);detail['feature']=c;separated.append(detail);value=detail['revised_violation_fraction']
        revised_fractions.append(value)
    support=max(revised_fractions,default=1.)
    scoped_valid=bool(scoped['finite_output'] and scoped['binary_masks'] and support<=1e-4 and not any(w['category']=='ConvergenceWarning' for w in notes))
    if source.startswith('learned_'):
        c=N['CFG'];f=scoped['variable_fraction']
        scoped_valid=bool(scoped_valid and scoped['observed_scope_coverage']==scoped['scope_size'] and f is not None and f>=c['learned_min_modeled_variable_fraction'] and scoped['activity_mean'] is not None and scoped['activity_mean']<=c['learned_max_zero_rate_mae'] and scoped['activity_p95']<=c['learned_zero_rate_p95_max'] and scoped['activity_max']<=c['learned_zero_rate_feature_max'])
    full=[]
    for col in N['VALUE_COLS']:
        # Compare the generated output with the exact prepared input actually supplied to the generator.
        a=prepared[col].to_numpy();b=out[col].to_numpy();bad=(~np.isfinite(b))|(b<a.min())|(b>a.max())
        full.append({'feature':col,'train_min':float(a.min()),'train_max':float(a.max()),'rows':len(b),'outside_count':int(bad.sum()),'outside_fraction':float(bad.mean()),'outside_examples':np.unique(b[bad])[:6].tolist()})
    maximum=max(r['outside_fraction'] for r in full)
    valid=bool(scoped_valid and maximum<=1e-4)
    return {'source_valid':valid,'reviewed_scoped_valid':scoped_valid,'original_scoped_check':scoped,
      'reviewed_scoped_max_support_violation':support,'full_output_range_valid':maximum<=1e-4,
      'full_output_max_range_violation':maximum,'full_output_range':full,'separated_membership_checks':separated,
      'scope_note':'Full prepared-input range is a generator implementation check, not physical calibration. Original learned fit scope remains separate.'}
