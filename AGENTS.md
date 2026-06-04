# QSDC Simulations

This project contains separate simulators for different QSDC papers.

- `<paper>/simulator/`: protocol logic for one paper.
- `<paper>/demo/`: runnable demos that show the protocol flow.
- `<paper>/benchmark/`: benchmark runners and generated run reports.
- `<paper>/tests/`: tests for that paper's simulator.
- `utils/`: paper-independent utilities, such as bit handling.

New papers should follow the same shape: keep the paper-specific simulator in
its own directory, share only genuinely reusable helpers through `utils/`, and
keep demos and benchmarks outside the simulator core.

## References

- `srikara`: S. Srikara, K. Thapliyal, and A. Pathak, Continuous variable direct secure quantum communication using gaussian states, Quantum Inf. Process. 19, 1 (2020).


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
