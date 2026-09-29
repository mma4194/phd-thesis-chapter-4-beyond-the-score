
# ============================================================
# 18. Figure data and publication-ready vector figures
# ============================================================
FD=PROFILE_ROOT/"figure_data"; FG=PROFILE_ROOT/"figures"
conf_long=CONFUSION.reset_index().melt(id_vars="expected_permission",var_name="observed_permission",value_name="count"); conf_long.to_csv(FD/"fig_known_truth_confusion.csv",index=False)
fig,ax=plt.subplots(figsize=(7.4,6.2)); mat=CONFUSION.to_numpy(float); im=ax.imshow(mat); ax.set_xticks(range(len(STATES))); ax.set_yticks(range(len(STATES))); ax.set_xticklabels(STATES,rotation=45,ha="right"); ax.set_yticklabels(STATES); ax.set_xlabel("Observed permission state"); ax.set_ylabel("Known-truth permission state"); ax.set_title("Full-stack known-truth terminal-state confusion")
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]): ax.text(j,i,str(int(mat[i,j])),ha="center",va="center")
fig.colorbar(im,ax=ax,label="Scenario × fixture count"); fig.tight_layout(); fig.savefig(FG/"fig_known_truth_confusion.pdf",bbox_inches="tight"); fig.savefig(FG/"fig_known_truth_confusion.png",dpi=220,bbox_inches="tight"); plt.close(fig)

rates=ABLATION_SUMMARY[["ablation","false_admission_rate_estimate","false_rejection_rate_estimate"]].copy(); rates.to_csv(FD/"fig_far_frr_by_ablation.csv",index=False); x=np.arange(len(rates)); w=.38
fig,ax=plt.subplots(figsize=(8.8,4.8)); ax.bar(x-w/2,rates.false_admission_rate_estimate,w,label="False admission"); ax.bar(x+w/2,rates.false_rejection_rate_estimate,w,label="False rejection"); ax.set_xticks(x); ax.set_xticklabels(rates.ablation,rotation=30,ha="right"); ax.set_ylabel("Rate"); ax.set_ylim(bottom=0); ax.set_title("Known-truth error rates under stage ablation"); ax.legend(); fig.tight_layout(); fig.savefig(FG/"fig_false_admission_rejection.pdf",bbox_inches="tight"); fig.savefig(FG/"fig_false_admission_rejection.png",dpi=220,bbox_inches="tight"); plt.close(fig)

acc=ABLATION_SUMMARY[["ablation","exact_permission_accuracy_estimate","full_label_accuracy_estimate"]].copy(); acc.to_csv(FD/"fig_stage_ablation_accuracy.csv",index=False)
fig,ax=plt.subplots(figsize=(8.8,4.8)); ax.bar(np.arange(len(acc)),acc.exact_permission_accuracy_estimate); ax.set_xticks(np.arange(len(acc))); ax.set_xticklabels(acc.ablation,rotation=30,ha="right"); ax.set_ylabel("Exact permission-state accuracy"); ax.set_ylim(0,1.05); ax.set_title("Contribution of each qualification stage"); fig.tight_layout(); fig.savefig(FG/"fig_stage_ablation.pdf",bbox_inches="tight"); fig.savefig(FG/"fig_stage_ablation.png",dpi=220,bbox_inches="tight"); plt.close(fig)

if len(SEVERITY_RESULTS):
    sev=SEVERITY_RESULTS.groupby(["intervention","severity"],as_index=False).agg(response_mean=("response","mean"),response_sd=("response","std"),n=("response","size")); sev.to_csv(FD/"fig_severity_response.csv",index=False)
    fig,ax=plt.subplots(figsize=(8.5,5.1))
    for name,g in sev.groupby("intervention"): ax.plot(g.severity,g.response_mean,marker="o",label=name)
    ax.set_xlabel("Planted severity"); ax.set_ylabel("Gate response / C2ST AUC"); ax.set_title("Known-truth severity response"); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(FG/"fig_severity_response.pdf",bbox_inches="tight"); fig.savefig(FG/"fig_severity_response.png",dpi=220,bbox_inches="tight"); plt.close(fig)
