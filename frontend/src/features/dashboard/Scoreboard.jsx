import TeamBadge from '../teams/TeamBadge.jsx';
import styles from './ClassPage.module.css';

export default function Scoreboard({ scoreboard }) {
  if (!scoreboard?.teams?.length) return null;
  if (scoreboard.cooperative) {
    return (
      <section className={styles.card} aria-labelledby="board-title">
        <h2 id="board-title">Group total</h2>
        <p className={styles.bigNumber}>{Math.round(scoreboard.group_points)} points together</p>
      </section>
    );
  }
  return (
    <section className={styles.card} aria-labelledby="board-title">
      <h2 id="board-title">Scoreboard</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Team</th>
            <th scope="col">Points</th>
            <th scope="col">Turns</th>
            <th scope="col">Best turn</th>
          </tr>
        </thead>
        <tbody>
          {scoreboard.teams.map((row) => (
            <tr key={row.team.id}>
              <th scope="row">
                <TeamBadge team={row.team} />
              </th>
              <td>{Math.round(row.points)}</td>
              <td>{row.turns}</td>
              <td>{Math.round(row.best)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
