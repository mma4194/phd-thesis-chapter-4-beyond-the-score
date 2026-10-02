
RUN_NEW_EXPERIMENTS = True  # <-- leave False until A/B have been reviewed

# Prespecified POSCTRL-1 severities. Do not tune these against TEST.
POSCTRL_SIGMA_IQR = {
    "mild": 0.02,
    "strong": 0.10,
}
TEMP_BLOCK_ROWS = 300  # used later in TEMPCTRL-1; fixed before TEST evaluation
print("RUN_NEW_EXPERIMENTS =",RUN_NEW_EXPERIMENTS)
print("RUN_C2ST_CAPACITY_DIAGNOSTIC =",RUN_C2ST_CAPACITY_DIAGNOSTIC)
print("POSCTRL_SIGMA_IQR =",POSCTRL_SIGMA_IQR)
