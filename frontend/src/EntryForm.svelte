<script>
  import { createEventDispatcher } from "svelte";

  export let equivalent = null; // { factor, baseline_mm, limit_mm }
  export let authHeaders = () => ({});

  const dispatch = createEventDispatcher();

  let chainage = "";
  let mode = "chord"; // chord=填弦长 / direct=直填毫米
  let chordMm = "";
  let deltaMm = "";
  let error = "";
  let loading = false;

  function round3(x) {
    return Math.round(x * 1000) / 1000;
  }

  $: chordNum = Number(chordMm);
  $: preview =
    mode === "chord" && equivalent && chordMm !== "" && !isNaN(chordNum)
      ? round3((chordNum - equivalent.baseline_mm) * equivalent.factor)
      : null;
  $: limit = equivalent?.limit_mm ?? 3.0;

  async function submit() {
    error = "";
    if (!chainage.trim()) {
      error = "桩号不能为空";
      return;
    }
    const body = { chainage: chainage.trim() };
    if (mode === "chord") {
      if (chordMm === "" || isNaN(chordNum)) {
        error = "弦长读数必须是数字";
        return;
      }
      body.chord_mm = chordNum;
    } else {
      const d = Number(deltaMm);
      if (deltaMm === "" || isNaN(d)) {
        error = "收敛值必须是数字";
        return;
      }
      body.delta_mm = d;
    }
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        return;
      }
      chainage = "";
      chordMm = "";
      deltaMm = "";
      dispatch("submitted");
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }
</script>

<style>
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  h2 { margin: 0 0 0.75rem; font-size: 1.05rem; color: #fcd34d; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  .field {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  .modes { display: flex; gap: 1.25rem; margin-bottom: 0.75rem; }
  .modes label { display: flex; align-items: center; gap: 0.35rem; cursor: pointer; margin: 0; }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  .err { color: #fb7185; }
  .hint { color: #a8a29e; font-size: 0.85rem; margin: -0.35rem 0 0.75rem; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
</style>

<section>
  <h2>录入读数</h2>
  <div class="modes">
    <label><input type="radio" bind:group={mode} value="chord" /> 填弦长（按当量换算）</label>
    <label><input type="radio" bind:group={mode} value="direct" /> 直填毫米</label>
  </div>
  <label>里程桩号</label>
  <input class="field" placeholder="例如 K20+050" bind:value={chainage} />
  {#if mode === "chord"}
    <label>弦长读数（mm）</label>
    <input class="field" type="number" step="0.001" bind:value={chordMm} />
    {#if preview !== null}
      <p class="hint">
        按当前当量换算 ≈ {preview} mm
        <span class="tag {Math.abs(preview) <= limit ? 'ok' : 'bad'}">
          {Math.abs(preview) <= limit ? "合格" : "超限"}
        </span>
      </p>
    {:else}
      <p class="hint">换算式：收敛 = (弦长 − 基准弦长) × 当量系数</p>
    {/if}
  {:else}
    <label>收敛（毫米，可正可负）</label>
    <input class="field" type="number" step="0.1" bind:value={deltaMm} />
  {/if}
  <button disabled={loading} on:click={submit}>提交（进入待认领）</button>
  {#if error}<p class="err">{error}</p>{/if}
</section>
