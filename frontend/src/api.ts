export async function runPricesJob() {
  const res = await fetch("http://127.0.0.1:8000/api/prices/run", {
    method: "POST",
  });

  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // JSONじゃない場合は無視
  }

  if (!res.ok) {
    console.error("API error:", res.status, data);
    throw new Error(`API error: status=${res.status}`);
  }

  return data;  // { status, asin_count, excel_path }
}
