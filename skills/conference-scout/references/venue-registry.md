# Venue Registry

Tier 1 = main sweep target. Tier 2 = cross-check only (or include if user asks for broader coverage).

```yaml
wearable_sensing:
  tier_1:
    - { name: UbiComp / IMWUT, dblp: https://dblp.org/db/journals/imwut/ }
    - { name: MobiCom,         dblp: https://dblp.org/db/conf/mobicom/ }
    - { name: MobiSys,         dblp: https://dblp.org/db/conf/mobisys/ }
    - { name: SenSys,          dblp: https://dblp.org/db/conf/sensys/ }
    - { name: IPSN,            dblp: https://dblp.org/db/conf/ipsn/ }
    - { name: CHI,             dblp: https://dblp.org/db/conf/chi/ }
  tier_2:
    - { name: ISWC,            dblp: https://dblp.org/db/conf/iswc/ }
    - { name: HotMobile,       dblp: https://dblp.org/db/conf/hotmobile/ }
    - { name: UIST,            dblp: https://dblp.org/db/conf/uist/ }

ai_ml:
  tier_1:
    - { name: NeurIPS, dblp: https://dblp.org/db/conf/nips/ }
    - { name: ICLR,    dblp: https://dblp.org/db/conf/iclr/ }
    - { name: ICML,    dblp: https://dblp.org/db/conf/icml/ }
    - { name: CVPR,    dblp: https://dblp.org/db/conf/cvpr/ }
  tier_2:
    - { name: AAAI,    dblp: https://dblp.org/db/conf/aaai/ }
    - { name: ACL,     dblp: https://dblp.org/db/conf/acl/ }
    - { name: EMNLP,   dblp: https://dblp.org/db/conf/emnlp/ }

iot_systems:
  tier_1:
    - { name: SenSys,          dblp: https://dblp.org/db/conf/sensys/ }
    - { name: MobiSys,         dblp: https://dblp.org/db/conf/mobisys/ }
    - { name: IPSN,            dblp: https://dblp.org/db/conf/ipsn/ }
    - { name: UbiComp / IMWUT, dblp: https://dblp.org/db/journals/imwut/ }
    - { name: MobiCom,         dblp: https://dblp.org/db/conf/mobicom/ }
    - { name: IoTDI,           dblp: https://dblp.org/db/conf/iotdi/ }
  tier_2:
    - { name: EuroSys,         dblp: https://dblp.org/db/conf/eurosys/ }
    - { name: HotMobile,       dblp: https://dblp.org/db/conf/hotmobile/ }
    - { name: CHI,             dblp: https://dblp.org/db/conf/chi/ }

eda_hardware:
  tier_1:
    - { name: DAC,             dblp: https://dblp.org/db/conf/dac/ }
    - { name: ICCAD,           dblp: https://dblp.org/db/conf/iccad/ }
    - { name: DATE,            dblp: https://dblp.org/db/conf/date/ }
    - { name: ASPLOS,          dblp: https://dblp.org/db/conf/asplos/ }
  tier_2:
    - { name: ISPD,            dblp: https://dblp.org/db/conf/ispd/ }
    - { name: ISLPED,          dblp: https://dblp.org/db/conf/islped/ }
    - { name: FPL,             dblp: https://dblp.org/db/conf/fpl/ }

security:
  tier_1:
    - { name: USENIX Security, dblp: https://dblp.org/db/conf/uss/ }
    - { name: CCS,             dblp: https://dblp.org/db/conf/ccs/ }
    - { name: IEEE S&P,        dblp: https://dblp.org/db/conf/sp/ }
    - { name: NDSS,            dblp: https://dblp.org/db/conf/ndss/ }
  tier_2:
    - { name: USENIX ATC,      dblp: https://dblp.org/db/conf/usenix/ }

systems:
  tier_1:
    - { name: OSDI,    dblp: https://dblp.org/db/conf/osdi/ }
    - { name: SOSP,    dblp: https://dblp.org/db/conf/sosp/ }
    - { name: EuroSys, dblp: https://dblp.org/db/conf/eurosys/ }
    - { name: ASPLOS,  dblp: https://dblp.org/db/conf/asplos/ }
  tier_2:
    - { name: USENIX ATC, dblp: https://dblp.org/db/conf/usenix/ }
    - { name: NSDI,       dblp: https://dblp.org/db/conf/nsdi/ }

hci:
  tier_1:
    - { name: CHI,  dblp: https://dblp.org/db/conf/chi/ }
    - { name: UIST, dblp: https://dblp.org/db/conf/uist/ }
  tier_2:
    - { name: CSCW, dblp: https://dblp.org/db/conf/cscw/ }
    - { name: IUI,  dblp: https://dblp.org/db/conf/iui/ }
```

## Topic → venue group auto-routing

| Topic signal | Group |
|---|---|
| wearable sensing, ExG, EEG/EMG, auditory wearables, AR glasses audio | `wearable_sensing` |
| machine learning, deep learning, representation learning | `ai_ml` |
| sensor systems, mobile systems, IoT platforms | `iot_systems` |
| adversarial attacks, sensor security, side channels | `security` + `iot_systems` |
| OS, storage, distributed systems | `systems` |
| human-computer interaction, user interfaces | `hci` |
| PCB design, EDA, chip design, RTL, layout, schematic, hardware automation | `eda_hardware` + `iot_systems` |
| LLM agent for hardware / embedded / IoT system design | `eda_hardware` + `iot_systems` + `ai_ml` |
| spans multiple buckets | union of all relevant tier lists |

When the topic clearly fits one of these, auto-select instead of asking. Ambiguous topics → ask which family.
