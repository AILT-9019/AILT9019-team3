async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
    } catch {
      // keep the status message
    }
    throw new Error(message);
  }
  return response;
}

export async function getHealth() {
  return (await request("/api/health")).json();
}

export async function getState() {
  return (await request("/api/state")).json();
}

export async function uploadFiles(files, courseHint) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  if (courseHint) form.append("course_hint", courseHint);
  return (await request("/api/uploads", { method: "POST", body: form })).json();
}

export async function pasteText({ title, courseHint, text }) {
  return (
    await request("/api/paste", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title || null,
        course_hint: courseHint || null,
        text,
      }),
    })
  ).json();
}

export async function startExtractions(uploadIds) {
  return (
    await request("/api/extractions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ upload_ids: uploadIds }),
    })
  ).json();
}

export async function getUploadText(uploadId) {
  return (await request(`/api/uploads/${encodeURIComponent(uploadId)}/text`)).text();
}
