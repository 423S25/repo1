# USER TESTING

## Test Design

For these tests, users were given the product and asked to explore its features without guidance or input. If a tester encountered an issue or got stuck, the problem was noted and explained by the tester. If they broke something or reached a bad endpoint, the app was restored to its previous state, and the bug was documented.

### Tasks Assigned to Testers
Each tester completed the following tasks:
- Create several new categories  
- Create several new products  
- Filter through different options in the table  
- Update product info  
- Delete a product  
- Update category info  
- Export to CSV  

Beyond these tasks, testers explored and interacted with the product freely based on their own curiosity and needs.

---

## Testers

### 1. Cody
- Tested by a family member at home.
- Brief explanation and user docs provided.
- Observations:
  - **Bug**: Deleting a product then refreshing causes a 404 error.
  - Delete and update buttons are unclear.
  - Buttons for donations vs. purchased are confusing (planned for removal).
  - User docs could be clearer.
- Feedback: Family member (50s, not tech-savvy) found the interface “pretty straightforward.”

### 2. Quinlin
- Tester: Math & Econ major.
- Observations:
  - Wanted screenshots and precise instructions.
  - User docs were too vague and outdated.
  - Inconsistent button placement (e.g., add category on right, edit/delete on left).
  - Mobile version was more intuitive.
  - Error messages lacked precision.

### 3. Teddy
- Tester: User’s mom.
- Observations:
  - Confusing unit type labels.
  - Unclear initial actions upon opening the app.

### 4. AJ
- Tester: User’s 90-year-old grandpa.
- Observations:
  - Didn’t break the app, but found some features non-intuitive.
  - Didn’t understand that a category must be made before adding a product.
  - Struggled with adjusting stock/product info.
  - Misunderstood top banner as a filter.
- Feedback: Reinforced need for intuitive design and clearer flows.

### 5. Matthew
- Tester: Electrical engineering major with no prior app knowledge.
- Observations:
  - Bug: Add product button wasn't working (later fixed).
  - No error when letters entered in number-only inputs.
  - Took time to complete some tasks.
  - Added products before categories (common mistake).
  - Export to CSV works even with no items in the database (doesn’t break, but may need review).

### 6. Emma
- Tester: Torie Keto (Graphic Design student).
- Observations:
  - Liked visuals on reports page.
  - Appreciated the mobile version.
  - Confused "New Product" button with edit function.
  - Misleading icons (look clickable but aren’t).
  - “New Product” label appears when updating—should say “Update”.
- Takeaway: Language and button labeling are critical for clarity.

### 7. Luke
- Tester: Fellow graphic design student.
- Observations:
  - Liked table with sliding stock bar.
  - Some button names were confusing.
  - Unclear what features existed at first glance.
- Overall: Positive experience, helped identify UX improvements.

---

## Summary

Each team member found a non-CS major to test the software. Testers received the URL but no instructions unless absolutely needed.

### Key Feedback:
- Need for more detailed instructions to understand the app.
- Layout and navigation were often unintuitive.
- User documentation is lacking and needs improvement.

### Lessons Learned:
- Improve and better link user documentation on the site.
- Add a tutorial or guide to the system.
- Fix bugs identified during testing.
- Add more specific error messages for forms and routes.
- Developer assumptions about "intuitive" features don’t always match user experience.
- Outside testers revealed overlooked bugs and pain points.

### Planned Improvements:
- Enhance and make user documentation more accessible.
- Adjust layout for better UX.
- Add custom error and 404 pages.
- Improve error messages for validation.
- Fix bugs discovered during testing.
