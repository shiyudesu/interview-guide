export class ReconnectTimer {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private active = true;

  activate(): void {
    this.active = true;
    this.cancel();
  }

  schedule(delay: number, callback: () => void): void {
    this.cancel();
    if (!this.active) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.active) callback();
    }, delay);
  }

  stop(): void {
    this.active = false;
    this.cancel();
  }

  private cancel(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
