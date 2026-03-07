 // sendMessage(), uploadFile()

 import httpClient from "./httpClient";

// Send a text-only chat message to the backend.
export const sendMessage = async (message, history = []) => {
  const { data } = await httpClient.post("/chat", { message, history });
  return data.response;
};

// Upload a file with a message to the backend chat upload endpoint.
export const uploadFile = async (file, message) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("message", message);

  const { data } = await httpClient.post("/chat/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return data;
};