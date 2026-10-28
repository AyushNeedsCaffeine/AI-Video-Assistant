(() => {
  const gsap = window.gsap;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!gsap || reduceMotion) return;

  const reveals = document.querySelectorAll("[data-reveal]");
  if (reveals.length) {
    gsap.from(reveals, {
      y: 16,
      opacity: 0,
      duration: 0.7,
      stagger: 0.07,
      ease: "power3.out",
      clearProps: "transform,opacity",
      immediateRender: false,
    });
  }

  const heroWrap = document.getElementById("hero-logo-wrap");
  const heroLogo = document.getElementById("hero-logo");
  if (heroWrap && heroLogo) {
    gsap.set(heroLogo, { transformPerspective: 900, transformOrigin: "50% 50%" });
    gsap.to(heroLogo, {
      y: -7,
      duration: 3.2,
      repeat: -1,
      yoyo: true,
      ease: "sine.inOut",
    });

    heroWrap.addEventListener("mousemove", (event) => {
      const rect = heroWrap.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      gsap.to(heroLogo, {
        rotateY: x * 12,
        rotateX: -y * 12,
        duration: 0.5,
        ease: "power2.out",
      });
    });

    heroWrap.addEventListener("mouseleave", () => {
      gsap.to(heroLogo, { rotateX: 0, rotateY: 0, duration: 0.6, ease: "power2.out" });
    });
  }

  const brandButton = document.querySelector(".brand-button");
  const brandMark = document.querySelector(".brand-mark");
  if (brandButton && brandMark) {
    brandButton.addEventListener("mouseenter", () => {
      gsap.to(brandMark, { rotate: 8, scale: 1.06, duration: 0.35, ease: "back.out(2)" });
    });
    brandButton.addEventListener("mouseleave", () => {
      gsap.to(brandMark, { rotate: 0, scale: 1, duration: 0.35, ease: "power2.out" });
    });
  }

  const animateChat = () => {
    const messages = document.querySelectorAll("#chat-panel .chat-message");
    if (!messages.length) return;
    gsap.from(messages, {
      y: 8,
      opacity: 0,
      duration: 0.35,
      stagger: 0.04,
      ease: "power2.out",
      clearProps: "transform,opacity",
      immediateRender: false,
    });
  };

  animateChat();
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail && event.detail.target && event.detail.target.id === "chat-panel") {
      animateChat();
    }
  });
})();
