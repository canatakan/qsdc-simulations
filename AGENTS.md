# QSDC Simulations

This project contains separate simulators for different QSDC papers.

- `src/qsdc/common/`: paper-independent utilities, such as bit handling and
  random-source interfaces.
- `src/qsdc/protocols/<paper>/simulator/`: protocol logic for one paper.
- `src/qsdc/protocols/<paper>/benchmark/`: benchmark configs, runners, metrics,
  and artifact writers.
- `tests/protocols/<paper>/`: tests for that paper's simulator.

New papers should follow the same shape: keep the paper-specific simulator in
its own directory, share only genuinely reusable helpers through
`src/qsdc/common/`, and keep demos and benchmarks outside the simulator core (in `demo.py` and `benchmark/`).
Benchmark output files should go to the configured output directory, not into
the source tree.

## References

- `srikara`: S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).
- `cao`: Z. Cao, L. Wang, K. Liang, G. Chai, and J. Peng, Continuous-variable quantum secure direct communication based on Gaussian mapping, Phys. Rev. Appl. 16, 024012 (2021). The paper in `main-papers/cao.pdf` is the reference; the 2023 realization paper is not.


## Protocols

### Srikara, Thapliyal, and Pathak (`srikara`)

Protocol: continuous-variable QSDC using Gaussian states.

1. Bob chooses random `alpha_j` and `s_j = r_j exp(i theta_j)` values, prepares
   `S(s_j)D(alpha_j)|0>` for `j = 1, ..., n`, and sends the block to Alice.

2. Alice randomly splits the received states into `n/2` control modes and
   `n/2` delayed modes. She stores the delayed modes and announces the control
   coordinates to Bob.

3. Bob announces `s_j` and `alpha_j` for the control coordinates. Alice applies
   `S^dagger(s_j) = S(-s_j)`, homodyne-measures the control modes, and checks
   whether the results match `Re(alpha_j)` or `Im(alpha_j)` within tolerance.

4. If the control check passes, Alice uses the delayed modes. She selects `n/4`
   message modes and `n/4` decoy modes.

5. For each message mode, Alice encodes a 3-bit symbol by choosing `m_A` from
   its interval and applying `D(beta_A)`, where `beta_A = m_A(1 + i)`. Decoy
   modes are left unchanged with the identity operation `I`.

    Message interval rule:

    ````text
    000 -> (-infinity, -3)
    001 -> (-3, -2)
    010 -> (-2, -1)
    011 -> (-1, 0)
    100 -> (0, 1)
    101 -> (1, 2)
    110 -> (2, 3)
    111 -> (3, infinity)
    ````

6. Alice sends the delayed sequence back to Bob. Bob applies `S^dagger(s_j)` to
the returned modes and homodyne-measures them.

7. Alice announces the decoy coordinates. Bob checks the decoys for disturbance,
removes them if the check passes, and decodes the remaining message modes by
mapping the recovered `m_A` values back to 3-bit symbols.

#### Formulas

Coherent state and displacement:

```text
|alpha> = D(alpha)|0>
D(alpha) = exp(alpha a^dagger - alpha* a)
D(beta)|alpha> = |beta + alpha>
```

Squeezing:

```text
S(s) = exp[1/2 (s* a^2 - s (a^dagger)^2)]
s = r exp(i theta)
S^dagger(s) = S(-s)
```

Squeezing and displacement relation:

```text
S(s)D(alpha) = D(beta)S(s)
beta = alpha cosh(r) + exp(i theta) alpha* sinh(r)
alpha = beta cosh(r) - exp(i theta) beta* sinh(r)
```

Bob's prepared state:

```text
|psi_j> = S(s_j)D(alpha_j)|0>
s_j = r_j exp(i theta_j)
```

Expected value after inverse squeezing for an unchanged control or decoy mode:

```text
S^dagger(s_j)|psi_j> = D(alpha_j)|0>
q_j = Re(alpha_j)
p_j = Im(alpha_j)
```

Alice's message displacement:

```text
beta_A = m_A(1 + i)
D(beta_A)
```

Message displacement seen after Bob's inverse squeezing:

```text
Delta_j = beta_A cosh(r_j) - exp(i theta_j) beta_A* sinh(r_j)
```

Measured message component:

```text
q_measured = Re(alpha_j) + Re(Delta_j)
p_measured = Im(alpha_j) + Im(Delta_j)
```

Recovered message contribution:

```text
Delta_q = q_measured - Re(alpha_j)
Delta_p = p_measured - Im(alpha_j)
```

If the measured axis is used with the corresponding response factor:

```text
m_A = Delta_axis / response_axis
```

where

```text
response_axis = axis component of
                cosh(r_j)(1 + i) - exp(i theta_j) sinh(r_j)(1 - i)
```

Finally:

```text
recovered m_A -> interval -> 3-bit symbol
```


### Cao, Wang, Liang, Chai, and Peng (`cao`)

Protocol: continuous-variable QSDC based on Gaussian mapping with two-mode
squeezed states. Quadratures are in shot-noise units (vacuum variance 1).

1. Alice squeezes x of beam 1 and p of beam 2, mixes them on a 50:50 beam
   splitter, keeps S1 and sends S2 to Bob.

2. Channel detection: Alice picks random positions, both measure x and p of
   their beam there, and Alice publishes her results. A position passes the
   inseparability test `X_m^2 + P_m^2 < 2`. If the failure rate is not below
   the threshold, the communication is terminated.

3. Authentication: the same test on positions Bob picks and announces.

4. Gaussian mapping of each block:
   (a) message uniformization, 0 -> 01/10 and 1 -> 00/11, alternately;
   (b) block uniformization, 0 -> 00/01 and 1 -> 10/11, at random;
   (c) the block is split into m boxes, and d random detection bits are
       inserted into each box at random positions;
   (d) an odd parity bit is appended to each box; it does not select the
       interval;
   (e) the box selects one of `2^(4k/nm + d)` equiprobable intervals of
       N(0, V_A), and G1' is any value of G1 inside it.

5. Alice modulates G1' on X of S1 and an independent Gaussian G2 on P, and
   sends the signal beam S_info to Bob.

6. Bob measures S_info jointly with S2.

7. Postprocessing: parameter estimation from G2, reconciliation, privacy
   amplification, then the inverse mapping.

#### Formulas

Squeezed vacua and beam splitter (Eqs. 1-4):

```text
x1 = e^-r x1(0),  p1 = e^r p1(0)
x2 = e^r x2(0),   p2 = e^-r p2(0)
X1 = (x1 + x2)/sqrt2,  P1 = (p1 + p2)/sqrt2
X2 = (x2 - x1)/sqrt2,  P2 = (p2 - p1)/sqrt2
```

Inseparability test (Eq. 5), with heterodyne outcomes:

```text
X_m = (x_A - x_B)/sqrt2,  P_m = (p_A + p_B)/sqrt2
X_m^2 + P_m^2 < 2
```

Joint measurement (Eq. 6), after Alice's modulation:

```text
X_m = (X_info - X2)/sqrt2 = e^-r x1(0) + G1'/sqrt2
P_m = (P_info + P2)/sqrt2 = e^-r p2(0) + G2/sqrt2
```

Equiprobable intervals for V_A = 8 (Table I):

```text
000 (-inf, -3.25]   001 (-3.25, -1.91]   010 (-1.91, -0.90]   011 (-0.90, 0]
100 (0, 0.90]       101 (0.90, 1.91]     110 (1.91, 3.25]     111 (3.25, inf)
```


Noise (shot-noise units, vacuum variance 1), from the shared baselines:

```text
thermal loss (T, nbar):  q -> sqrt(T) q + sqrt((1 - T)(2 nbar + 1)) v
detector (eta, v_el):    q -> sqrt(eta) q + sqrt(1 - eta) v + sqrt(v_el) e
S1: Alice's delay OD1 -> D(G1' + i G2) -> fibre
S2: fibre -> Bob's delay OD2
checks: S1 after OD1, S2 after the fibre
```
