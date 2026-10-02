
# ============================================================
# 9. Publication-quality forensic figure + figure data
# ============================================================
# Figure data are always written separately.
fig1=DGP_AUDIT[["fixture_seed","regime","router_packets_slope","ota_frames_slope",
                "corr_router_packets_power","corr_ota_frames_power","r2_within_regime_ols"]].copy()
fig2=DERIVATION.copy()
fig1.to_csv(FORENSIC_ROOT/"figure_data"/"fig_KT10_regime_coefficients.csv",index=False)
fig2.to_csv(FORENSIC_ROOT/"figure_data"/"fig_KT10_stage3_relative_vs_absolute.csv",index=False)

# Panel A: slopes by regime.
fig,ax=plt.subplots(figsize=(7.2,4.2))
x=np.arange(len(FIXTURE_SEEDS)); w=.36
r0=DGP_AUDIT[DGP_AUDIT.regime==0].set_index("fixture_seed").loc[FIXTURE_SEEDS]
r1=DGP_AUDIT[DGP_AUDIT.regime==1].set_index("fixture_seed").loc[FIXTURE_SEEDS]
ax.bar(x-w/2,r0["router_packets_slope"],w,label="Regime 0")
ax.bar(x+w/2,r1["router_packets_slope"],w,label="Regime 1")
ax.axhline(0,linewidth=.8)
ax.set_xticks(x); ax.set_xticklabels([str(s) for s in FIXTURE_SEEDS])
ax.set_xlabel("Fixture seed"); ax.set_ylabel("OLS slope: router packets → IoT power")
ax.set_title("KT10 planted relationship reversal")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(FORENSIC_ROOT/"figures"/"fig_KT10_regime_slope_reversal.pdf",bbox_inches="tight")
fig.savefig(FORENSIC_ROOT/"figures"/"fig_KT10_regime_slope_reversal.png",dpi=220,bbox_inches="tight")
plt.show()

# Panel B: relative Stage-3 statistic versus absolute matched-real skill.
fig,ax=plt.subplots(figsize=(7.2,4.2))
x=np.arange(len(FIXTURE_SEEDS)); w=.36
ax.bar(x-w/2,DERIVATION["property_decision_estimate"],w,label="Relative log loss-ratio estimate")
ax.bar(x+w/2,DERIVATION["median_absolute_reference_skill_gain"],w,label="Absolute reference skill gain")
ax.axhline(0,linewidth=.8)
ax.set_xticks(x); ax.set_xticklabels([str(s) for s in FIXTURE_SEEDS])
ax.set_xlabel("Fixture seed")
ax.set_title("Relative equivalence passes despite poor absolute transfer")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(FORENSIC_ROOT/"figures"/"fig_KT10_relative_vs_absolute.pdf",bbox_inches="tight")
fig.savefig(FORENSIC_ROOT/"figures"/"fig_KT10_relative_vs_absolute.png",dpi=220,bbox_inches="tight")
plt.show()
