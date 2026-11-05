# 310-5 T18 fsync budget decision — 2026-11-05

Status: software budget decision only. This does not qualify the target host filesystem or physical STOP.

## Adopted profile parameters

- Stage budget: 10,000 ms.
- STOP reserve: 1,000 ms.
- Additional margin: 1,000 ms.
- Persistence profile ceiling after reserve and margin: strictly less than 8,000 ms for both p99.9 and maximum paired file-fsync + directory-fsync latency.

Rationale: the host protocol STOP writer has a 250 ms caller deadline. A 1,000 ms reserve is four times that software deadline. The separate 1,000 ms margin is retained for workload variation and measurement uncertainty. The reserve is not available to RawLog persistence. If the independent STOP writer topology is not available, this budget does not make STOP independent or physically qualified.

## Preliminary non-target profile

A 10,000-sample run was executed in the ChatGPT execution container only, on an overlay filesystem. Parameters were stage=10,000 ms, STOP reserve=1,000 ms, margin=1,000 ms.

- File fsync p99.9: 3.497 ms; max: 25.200 ms.
- Directory fsync p99.9: 28.710 ms; max: 427.048 ms.
- Paired file + directory fsync p99.9: 29.047 ms; max: 427.369 ms.
- No file or directory fsync failures.
- Paired p99.9 + margin: 1,029.047 ms.
- Paired max + margin: 1,427.369 ms.
- Both are below the 9,000 ms stage budget remaining after the STOP reserve.

This is only a script/sanity baseline. The execution container's overlay filesystem, mount options, kernel, storage device, and load are not the approved target host/storage and must not be substituted for the user's Linux host result.

## T18 status

T18 remains NOT RUN on the approved target host/storage. The 10,000-sample profile must be run on the target path with the adopted 1,000 ms STOP reserve and 1,000 ms margin. A target profile failure blocks acceptance. This decision does not establish physical STOP latency, power-loss durability, BOD behavior, current limit, or hardware interoperability.
