import { NextRequest, NextResponse } from "next/server";

// Authentication is resolved client-side by AuthProvider through the real
// backend session. Edge redirects based on a cosmetic cookie caused protected
// pages to flash and bounce to /login while Render was waking up.
export function proxy(_request: NextRequest) {
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"] };
