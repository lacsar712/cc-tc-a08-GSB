<script>
  import { onMount } from "svelte";
  import SubmitPanel from "./SubmitPanel.svelte";

  export let session;
  export let registerRefresh; // (fn) => void：让父组件统一轮询刷新

  let setting = null;
  let ledger = [];
  let coeffInput = "";
  let coeffError = "";
  let coeffOk = "";
  let saving = false;

  $: isWriter = session?.role === "writer";

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function refresh() {
    const [sRes, lRes] = await Promise.all([
      fetch("/api/equivalent", { headers: headers() }),
      fetch("/api/ledger", { headers: headers() }),
    ]);
    if (sRes.ok) {
      setting = await sRes.json();
      if (coeffInput === "") coeffInput = String(setting.coefficient);
    }
    if (lRes.ok) ledger = await lRes.json();
  }

  onMount(() => {
    refresh();
    registerRefresh(refresh);
  });

  async function saveCoeff() {
    coeffError = "";
    coeffOk = "";
    saving = true;
    try {
      const res = await fetch("/api/equivalent", {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({ coefficient: Number(coeffInput) }),
      });
      const data = await res.json();
      if (!res.ok) {
        // 当量填错或越界：后台退回并把原因说清楚。
        coeffError = data.detail || "保存失败";
        return;
      }
      setting = data;
      coeffInput = String(data.coefficient);
      coeffOk = "当量系数已更新";
      await refresh();
    } catch {
      coeffError = "保存时网络异常";
    } finally {
      saving = false;
    }
  }

  async function onSubmitted() {
    coeffOk = "";
    await refresh();
  }
</script>

<section class="panel">
  <h2>维护当量参数</h2>
  <p class="hint">
    换算关系：收敛(mm) = 弦长(mm) × 当量系数。弦长读数必须先换成收敛毫米再判合格。
  </p>
  {#if setting}
    {#if isWriter}
      <label>当量系数（必须为正）</label>
      <div class="row">
        <input type="number" step="0.000001" min="0" bind:value={coeffInput} />
        <button disabled={saving} on:click={saveCoeff}>保存当量</button>
      </div>
      <p class="hint">
        当前生效：{setting.coefficient}（{setting.updated_by} 于
        {setting.updated_at ? new Date(setting.updated_at).toLocaleString() : "—"} 更新）
      </p>
      {#if coeffError}<p class="err">{coeffError}</p>{/if}
      {#if coeffOk}<p class="ok">{coeffOk}</p>{/if}
    {:else}
      <p class="readonly">
        巡检员只读：当前当量系数 <strong>{setting.coefficient}</strong>
        （{setting.updated_by} 于
        {setting.updated_at ? new Date(setting.updated_at).toLocaleString() : "—"} 更新），不能修改。
      </p>
    {/if}
  {/if}
</section>

{#if isWriter}
  <SubmitPanel token={session.token} on:done={onSubmitted} />
{:else}
  <section class="panel">
    <h2>交读数进单</h2>
    <p class="readonly">巡检员为只读账号，不能提交读数；可在下方查看换算流水。</p>
  </section>
{/if}

<section class="panel">
  <h2>换算流水</h2>
  <p class="hint">每一条进队记录都在同一事务、同一拍落下对应一条流水。</p>
  <table>
    <thead>
      <tr>
        <th>流水号</th><th>记录号</th><th>桩号</th><th>来路</th>
        <th>弦长mm</th><th>当量</th><th>收敛mm</th><th>提交人</th><th>时间</th>
      </tr>
    </thead>
    <tbody>
      {#each ledger as row}
        <tr>
          <td>{row.id}</td>
          <td>{row.log_id}</td>
          <td>{row.chainage}</td>
          <td>{row.input_mode === "chord" ? "弦长路" : "毫米路"}</td>
          <td>{row.chord_mm ?? "—"}</td>
          <td>{row.coefficient ?? "—"}</td>
          <td>{row.delta_mm}</td>
          <td>{row.created_by}</td>
          <td>{new Date(row.created_at).toLocaleString()}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .panel {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  .panel h2 { margin: 0 0 0.25rem; font-size: 1.05rem; color: #fbbf24; }
  .hint { color: #a8a29e; font-size: 0.82rem; margin: 0 0 0.75rem; }
  .readonly { color: #d6d3d1; font-size: 0.9rem; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  .row { display: flex; gap: 0.6rem; align-items: center; }
  input {
    flex: 1; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .err { color: #fb7185; }
  .ok { color: #86efac; }
  table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; white-space: nowrap; }
</style>
