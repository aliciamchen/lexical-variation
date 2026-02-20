# Holistic testing plan

Do one playwright run, production mode, with the following specifications: 

1. Remove tajriba file if it exists
2. Social + mixed condition
3. 15 people log on to the experiment and do the intro steps
4. 3 people cant pass the comprehension check and go to the screen that says that they failed the checks
5. The first 9 people who pass the comprehension check get assigned to an experiment
6. Experiment starts; the other 3 people go to the screen that says we couldn't find them a partner
7. The 9 people play through the experiment, with the speakers and listeners both sending messages and the listeners selecting tangrams. In Phase 1, one speaker from one group times out and the speaker role is reassigned; one listener from another group times out at a different time. 
8. Therefore 7 people proceed to the second phase. In the second phase, another member of the two-member groups (bc of timeouts in the first phase) times out so the third member of that group is also removed. Make sure to check reshuffling is correct and the third member goes to the correct exit screen. 
9. Then there are 5 members in the third phase, and they keep on going until the end, with reshuffling 
10. The remaining five members make it to the end and fill out the exit survey. 

Check all the screens are correct and the timeouts and reassignments are behaving correctly, and that people move to the right screens. 
Unless its the cases where they time out, just have them click through the experiment quickly so that the test moves faster. 

## Data checks

Run `empirica export`, visualize the data

- Check that data saving is correct with the dropouts
- Check that it tracks the reshuffling
