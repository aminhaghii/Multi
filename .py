import matplotlib.pyplot as plt

def draw_comparison_problem_4():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # --- نمودار سمت چپ (فرآیند 1) ---
    years1 = range(0, 6)
    ax1.plot(years1, [0]*len(years1), color='black', linewidth=1.5)
    
    A_val = 494 # مقدار محاسبه شده گرد شده
    
    for y in range(1, 5):
        ax1.arrow(y, 0, 0, A_val, head_width=0.15, head_length=30, fc='blue', ec='blue', length_includes_head=True)
        ax1.text(y, A_val + 40, "A", ha='center', va='bottom', color='blue', fontweight='bold')
    
    ax1.set_title("(1) سری یکنواخت مجهول", fontsize=14)
    ax1.set_ylim(-100, 900)
    ax1.set_xticks(range(6))
    ax1.set_yticks([])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.spines['bottom'].set_position('zero')
    ax1.text(2.5, -80, f"A ≈ {A_val}", ha='center', color='red', fontsize=12)


    # --- نمودار سمت راست (فرآیند 2) ---
    years2 = range(0, 7)
    ax2.plot(years2, [0]*len(years2), color='black', linewidth=1.5)
    
    flows2 = {1: 150, 2: 300, 3: 450, 4: 600, 5: 750}
    
    for y, amt in flows2.items():
        ax2.arrow(y, 0, 0, amt, head_width=0.15, head_length=30, fc='green', ec='green', length_includes_head=True)
        ax2.text(y, amt + 40, f"{amt}", ha='center', va='bottom', color='green', fontweight='bold')

    ax2.set_title("(2) سری گرادیان معلوم", fontsize=14)
    ax2.set_ylim(-100, 900)
    ax2.set_xticks(range(7))
    ax2.set_yticks([])
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['bottom'].set_position('zero')
    ax2.text(3, -80, "PW = 1500.27", ha='center', color='green', fontsize=12)

    plt.tight_layout()
    plt.show()

draw_comparison_problem_4()