 // sendMessage(), uploadFile()

 import httpClient from "./httpClient";
import { persistentChatApi } from "./conversationApi";

// Send a text-only chat message to the backend (persistent).
// Returns: { conversation_id, public_id, message_id, response }
export const sendMessage = async (message, conversation_id = null) => {
  const { data } = await persistentChatApi.send(message, conversation_id);
  return data;  // Return full object, not just response
};

// Upload a file with a message to the backend (persistent).
export const uploadFile = async (file, message = "", conversation_id = null) => {
  const { data } = await persistentChatApi.upload(file, message, conversation_id);
  return data;
};

// Confirm an extracted invoice payload (future backend route).
export const confirmInvoice = async (payload) => {
  const { data } = await httpClient.post("/invoice/confirm", payload);
  return data;
};

export const searchPartners = async ({ name, role = "any", limit = 8 }) => {
  const { data } = await httpClient.get("/invoice/partners/search", {
    params: { name, role, limit },
  });
  return data;
};