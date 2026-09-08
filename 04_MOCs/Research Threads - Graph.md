---
type: moc
name: "Research Threads - Graph"
aliases:
  - Thread network graph
created: "2026-09-07"
tags:
  - moc
  - drosophila
  - graph
  - evo-devo
---

# Research Threads — Network Graph

> Visual network of the vault's research literature, grouped into the four research
> threads and connected by the paper-to-paper relationships documented in the
> literature reviews in `08_Reviews`. Rendered natively by Obsidian (Mermaid).
>
> - **Thread 1** — GRN co-option & morphological novelty (blue)
> - **Thread 2** — *doublesex* / sex determination (green)
> - **Thread 3** — evo-devo, rapid divergence & sexual selection (purple)
> - **Thread 4** — comparative atlases & standardized nomenclature (orange)

```mermaid
graph LR
    %% ===== Thread hubs =====
    T1["Thread 1 · GRN co-option & novelty"]
    T2["Thread 2 · doublesex / sex determination"]
    T3["Thread 3 · evo-devo & sexual selection"]
    T4["Thread 4 · atlases & nomenclature"]

    %% ===== Thread 1 =====
    subgraph THREAD1[Thread 1 · GRN co-option & novelty]
        G2015["Glassford 2015"]
        S2025["Shodja 2025"]
        R2024TC["Rice 2024 · trichome"]
        R2023PH["Rice 2023 · phallus"]
    end

    %% ===== Thread 2 =====
    subgraph THREAD2[Thread 2 · doublesex / sex determination]
        K2000["Kopp 2000"]
        W2008["Williams 2008"]
        T2011["Tanaka 2011"]
        R2018["Rice 2018"]
        K2012["Kopp 2012"]
        H2021["Hopkins & Kopp 2021"]
        T2009["Tanaka 2009"]
    end

    %% ===== Thread 3 =====
    subgraph THREAD3[Thread 3 · evo-devo & sexual selection]
        K2002["Kopp & True 2002"]
        M2020["Massey 2020"]
    end

    %% ===== Thread 4 =====
    subgraph THREAD4[Thread 4 · atlases & nomenclature]
        V2019["Vincent 2019"]
        R2019AM["Rice 2019 · male atlas"]
        M2022FA["McQueen 2022 · female atlas"]
        U2024["Urum 2024"]
        P2025["McQueen 2025 · parallels"]
        T2022SU["Tanaka 2022 · suzukii"]
    end

    %% ===== Hub -> paper membership =====
    T1 --- G2015 & S2025 & R2024TC & R2023PH
    T2 --- K2000 & W2008 & T2011 & R2018 & K2012 & H2021 & T2009
    T3 --- K2002 & M2020
    T4 --- V2019 & R2019AM & M2022FA & U2024 & P2025 & T2022SU

    %% ===== Cross-thread paper relationships (from the reviews) =====
    G2015 --- S2025
    G2015 --- R2024TC
    G2015 --- R2023PH
    S2025 --- R2024TC
    S2025 --- R2023PH
    R2024TC --- T2022SU
    R2023PH --- K2002
    K2000 --- W2008
    W2008 --- T2011
    T2011 --- T2009
    T2011 --- R2018
    T2011 --- P2025
    K2012 --- H2021
    H2021 --- W2008
    K2002 --- M2020
    R2019AM --- M2022FA
    R2019AM --- V2019
    R2019AM --- U2024
    V2019 --- P2025
    M2022FA --- P2025
    M2022FA --- T2022SU
    U2024 --- P2025

    %% ===== Styling by thread =====
    classDef t1 fill:#dbe7f6,stroke:#2f6db3,color:#0b2e52
    classDef t2 fill:#d9ecd9,stroke:#3a8f3a,color:#104211
    classDef t3 fill:#e8dcf2,stroke:#7a3fb0,color:#3c1d5e
    classDef t4 fill:#fdebd3,stroke:#d07f20,color:#5e3a0a
    classDef hub fill:#f5f0e6,stroke:#8a8272,color:#3a3529

    class T1,T2,T3,T4 hub
    class G2015,S2025,R2024TC,R2023PH t1
    class K2000,W2008,T2011,R2018,K2012,H2021,T2009 t2
    class K2002,M2020 t3
    class V2019,R2019AM,M2022FA,U2024,P2025,T2022SU t4
```

## How to read this graph

- **Thread hubs** (light boxes) group each paper into its primary research thread.
- **Edges between papers** are the paper-to-paper relationships documented in the
  `08_Reviews` literature reviews — not asserted from titles.
- Papers sitting at the junction (`Rice 2023 phallus` ↔ `Kopp & True 2002`,
  `Tanaka 2022 suzukii` ↔ `Rice 2024 trichome`, `Tanaka 2011` ↔ `McQueen 2025
  parallels`) are the **connective tissue** bridging threads.

## Related

- [[Research Threads - MOC]] — textual synthesis with full wikilinks & citations
- [[Drosophila Terminalia - MOC]]
- `references/papers_thread_index.csv` — machine-readable paper → thread table