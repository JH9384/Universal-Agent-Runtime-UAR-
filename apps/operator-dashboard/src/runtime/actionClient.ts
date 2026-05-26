export async function sendOperatorAction(action: string): Promise<void> {
  await fetch(`/runtime/actions/${action}`, {
    method: 'POST',
  });
}
