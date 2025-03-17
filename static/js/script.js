// Enhance animations with Framer Motion (if needed)
document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".bg-white");
  cards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      card.style.transform = "scale(1.02)";
    });
    card.addEventListener("mouseleave", () => {
      card.style.transform = "scale(1)";
    });
  });
});
