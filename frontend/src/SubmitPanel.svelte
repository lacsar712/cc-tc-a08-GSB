<script>
  import { createEventDispatcher } from "svelte";

  export let token = "";
  export let disabled = false;

  const dispatch = createEventDispatcher();

  let chainage = "";
  let inputMode = "chord"; // chord=交弦长后台换算；delta=直填毫米
  let chordMm = "";
  let deltaMm = "";
  let preview = null;
  let error = "";
  let previewError = "";
  let loading = false;

  function headers() {
    return { Authorization: "Bearer " + token };
  }

  function switchMode(mode) {
    inputMode = mode;
    preview = null;
    previewError = "";
    error = "";
  }

  async function runPreview() {
    previewError = "";
    preview = null;
    const payload =
      inputMode === "chord"
        ? { chord_mm: Number(chordMm) }
        : { delta_mm: Number(deltaMm) };
    try {
      const res = await fetch("/api/equivalent/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        previewError = data.detail || "试算失败";
        return;
      }
      preview = data;
    } catch {
      previewError = "试算时网络异常";
    }
  }

  async function submit() {
    error = "";
    if (!chainage.trim()) {
      error = "桩号不能为空";
      return;
    }
    const payload = { chainage: chainage.trim() };
    if (inputMode === "chord") {
      if (chordMm === "") {
        error = "请填写弦长读数";
        return;
      }
      payload.chord_mm = Number(chordMm);
    } else {
      if (deltaMm === "") {
        error = "请填写收敛毫米";
        return;
      }
      payload.delta_mm = Number(deltaMm);
    }
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        // 当量填错或越界时，后台把原因说清楚原样退回到这里。
        error = data.detail || "提交失败";
        return;
      }
      chainage = "";
      chordMm = "";
      deltaMm = "";
      preview = null;
      dispatch("done", data);
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }
</script>

<section class="panel">
  <h2>交读数进单</h2>
  <p class="hint">弦长读数不能直接当毫米：弦长路由后台按当前当量系数换算成收敛再判定；直填毫米路不换算。两路算出同一个收敛数。</p>

  <div class="modes">
    <button
      class="mode {inputMode === 'chord' ? 'active' : ''}"
      on:click={() => switchMode("chord")}
      type="button"
    >弦长路（填弦长）</button>
    <button
      class="mode {inputMode === 'delta' ? 'active' : ''}"
      on:click={() => switchMode("delta")}
      type="button"
    >毫米路（直填毫米）</button>
  </div>

  <label>里程桩号</label>
  <input placeholder="例如 K20+050" bind:value={chainage} />

  {#if inputMode === "chord"}
    <label>弦长读数（mm，仪器读数）</label>
    <input type="number" step="0.001" bind:value={chordMm} />
  {:else}
    <label>收敛（毫米，可正可负）</label>
    <input type="number" step="0.1" bind:value={deltaMm} />
  {/if}

  <div class="row">
    <button class="ghost" type="button" on:click={runPreview}>试算换算</button>
    <button disabled={loading || disabled} on:click={submit} type="button">提交（进入待认领）</button>
  </div>

  {#if preview}
    <div class="preview">
      {#if preview.input_mode === "chord"}
        试算：弦长 {preview.chord_mm} mm × 当量 {preview.coefficient}
        = 收敛 <strong>{preview.delta_mm}</strong> mm
      {:else}
        试算：直填收敛 <strong>{preview.delta_mm}</strong> mm（不经过当量换算）
      {/if}
    </div>
  {/if}
  {#if previewError}<p class="err">{previewError}</p>{/if}
  {#if error}<p class="err">{error}</p>{/if}
  {#if disabled}<p class="hint">巡检员为只读账号，不能提交读数。</p>{/if}
</section>

<style>
  .panel h2 { margin: 0 0 0.25rem; font-size: 1.05rem; color: #fbbf24; }
  .hint { color: #a8a29e; font-size: 0.82rem; margin: 0 0 0.75rem; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  .modes { display: flex; gap: 0.5rem; margin-bottom: 0.9rem; }
  .mode {
    cursor: pointer; padding: 0.4rem 0.8rem; border-radius: 6px; border: 1px solid #57534e;
    background: #0c0a09; color: #d6d3d1; font-size: 0.85rem;
  }
  .mode.active { border-color: #d97706; background: #7c2d12; color: #fed7aa; font-weight: 600; }
  .row { display: flex; gap: 0.6rem; }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .ghost { background: #57534e; }
  .preview {
    margin-top: 0.75rem; padding: 0.55rem 0.7rem; border-radius: 6px;
    background: #14532d; color: #bbf7d0; font-size: 0.88rem;
  }
  .err { color: #fb7185; }
</style>
