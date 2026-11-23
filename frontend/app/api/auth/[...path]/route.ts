import { handleAccountWrite } from "@/lib/server/apiProxy";

export async function POST(request: Request) {
  return handleAccountWrite(request);
}

export async function PUT(request: Request) {
  return handleAccountWrite(request);
}

export async function PATCH(request: Request) {
  return handleAccountWrite(request);
}

export async function DELETE(request: Request) {
  return handleAccountWrite(request);
}
