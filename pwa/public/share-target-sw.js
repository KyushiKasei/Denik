self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "POST" || url.pathname !== "/share") {
    return;
  }
  event.respondWith(
    (async () => {
      const form = await event.request.formData();
      const cache = await caches.open("pamatky-share");
      const keys = await cache.keys();
      await Promise.all(keys.map((request) => cache.delete(request)));
      const maxBytes = 80 * 1024 * 1024;
      const maxFiles = 40;
      const files = form
        .getAll("media")
        .filter((item) => item instanceof File && item.size > 0 && item.size <= maxBytes)
        .slice(0, maxFiles);
      const meta = {
        title: String(form.get("title") || ""),
        text: String(form.get("text") || ""),
        url: String(form.get("url") || ""),
        count: files.length,
      };
      await cache.put(
        "/__share/meta",
        new Response(JSON.stringify(meta), { headers: { "content-type": "application/json" } }),
      );
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        if (!(file instanceof File)) {
          continue;
        }
        await cache.put(
          `/__share/${index}`,
          new Response(file, {
            headers: {
              "content-type": file.type || "application/octet-stream",
              "x-filename": encodeURIComponent(file.name || `share-${index}.jpg`),
            },
          }),
        );
      }
      return Response.redirect("/import?shared=1", 303);
    })(),
  );
});
