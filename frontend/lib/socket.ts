"use client";

import { io, Socket } from "socket.io-client";
import { API_BASE_URL, WS_BASE_URL } from "./api";

let socket: Socket | null = null;
let currentToken: string | null = null;

export function getSocket(token: string): Socket {
  if (socket && currentToken === token) return socket;
  if (socket) socket.disconnect();

  const baseUrl = WS_BASE_URL || API_BASE_URL || window.location.origin;
  const httpBaseUrl = baseUrl.replace(/^ws/, "http");
  currentToken = token;
  socket = io(httpBaseUrl, {
    path: "/socket.io",
    auth: { token },
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 10000,
  });
  return socket;
}

export function disconnectSocket(): void {
  socket?.disconnect();
  socket = null;
  currentToken = null;
}
